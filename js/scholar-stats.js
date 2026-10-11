// Fills in the sidebar research stats and the per-paper citation buttons from Semantic Scholar.
// Totals are computed from the per-paper counts of only the papers listed on this page (those with
// a citation button), because the Semantic Scholar profile also holds papers by other authors,
// its author-level citationCount/hIndex lag behind, and it does not report an i10-index at all.
//
// Fallbacks, best first: a fresh response; the last response this browser saved (shown right away
// and kept if the refresh fails); the snapshot numbers written into the HTML. A paper missing from
// a response keeps whatever count is already on the page instead of dropping out of the totals.
document.addEventListener('DOMContentLoaded', function() {
  const statsBox = document.getElementById('researchStats');
  const authorId = statsBox && statsBox.dataset.s2Author;
  if (!authorId) {
    return;
  }

  const cacheKey = 's2-papers:' + authorId;
  const freshMs = 6 * 60 * 60 * 1000;
  const retryDelayMs = 2000;
  const apiUrl = 'https://api.semanticscholar.org/graph/v1/author/' + authorId + '?fields=papers.citationCount';

  const buttons = Array.from(document.querySelectorAll('.citation-button[data-s2-paper]'));

  function shownCount(button) {
    return parseInt(button.querySelector('.citation-count').textContent.replace(/,/g, ''), 10);
  }

  function render(papers) {
    const countById = {};
    papers.forEach(function(paper) {
      countById[paper.paperId] = paper.citationCount || 0;
    });

    const counts = buttons.map(function(button) {
      const count = countById[button.dataset.s2Paper];
      return count === undefined ? shownCount(button) : count;
    });

    buttons.forEach(function(button, i) {
      button.querySelector('.citation-count').textContent = counts[i].toLocaleString('en-US');
      button.querySelector('.citation-label').textContent = counts[i] === 1 ? 'citation' : 'citations';
    });

    const sorted = counts.slice().sort(function(a, b) { return b - a; });
    const stats = {
      citations: sorted.reduce(function(sum, c) { return sum + c; }, 0),
      h: sorted.filter(function(c, i) { return c >= i + 1; }).length,
      i10: sorted.filter(function(c) { return c >= 10; }).length
    };
    statsBox.querySelectorAll('[data-stat]').forEach(function(el) {
      el.textContent = stats[el.dataset.stat].toLocaleString('en-US');
    });
  }

  // Retries once, since the unauthenticated API occasionally rate-limits (429) or times out.
  function fetchPapers(retriesLeft) {
    return fetch(apiUrl)
      .then(function(response) {
        if (!response.ok) {
          throw new Error('Semantic Scholar returned ' + response.status);
        }
        return response.json();
      })
      .then(function(data) {
        if (!data || !Array.isArray(data.papers)) {
          throw new Error('Unexpected response from Semantic Scholar');
        }
        return data.papers;
      })
      .catch(function(error) {
        if (retriesLeft <= 0) {
          throw error;
        }
        return new Promise(function(resolve) { setTimeout(resolve, retryDelayMs); })
          .then(function() { return fetchPapers(retriesLeft - 1); });
      });
  }

  // Storage can throw in private windows or when site data is blocked, so it is best-effort.
  let cached = null;
  try {
    cached = JSON.parse(localStorage.getItem(cacheKey));
  } catch (e) {}

  if (cached && Array.isArray(cached.papers)) {
    render(cached.papers);
    if (Date.now() - cached.time < freshMs) {
      return;
    }
  }

  fetchPapers(1)
    .then(function(papers) {
      render(papers);
      try {
        localStorage.setItem(cacheKey, JSON.stringify({ time: Date.now(), papers: papers }));
      } catch (e) {}
    })
    .catch(function() {});
});
