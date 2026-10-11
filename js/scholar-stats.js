// Fills in the sidebar research stats and the per-paper citation buttons from Semantic Scholar.
// The numbers already in the HTML are a snapshot, shown if the request fails or is rate-limited.
// Totals are computed from the per-paper counts of only the papers listed on this page (those with
// a citation button), because the Semantic Scholar profile also holds papers by other authors,
// its author-level citationCount/hIndex lag behind, and it does not report an i10-index at all.
document.addEventListener('DOMContentLoaded', function() {
  const statsBox = document.getElementById('researchStats');
  const authorId = statsBox && statsBox.dataset.s2Author;
  if (!authorId) {
    return;
  }

  const cacheKey = 's2-papers:' + authorId;
  const cacheMs = 6 * 60 * 60 * 1000;
  const apiUrl = 'https://api.semanticscholar.org/graph/v1/author/' + authorId + '?fields=papers.citationCount';

  const buttons = document.querySelectorAll('.citation-button[data-s2-paper]');

  function render(papers) {
    const countById = {};
    papers.forEach(function(paper) {
      countById[paper.paperId] = paper.citationCount || 0;
    });

    const counts = Array.from(buttons)
                        .map(function(button) { return countById[button.dataset.s2Paper]; })
                        .filter(function(count) { return count !== undefined; })
                        .sort(function(a, b) { return b - a; });
    const stats = {
      citations: counts.reduce(function(sum, c) { return sum + c; }, 0),
      h: counts.filter(function(c, i) { return c >= i + 1; }).length,
      i10: counts.filter(function(c) { return c >= 10; }).length
    };
    statsBox.querySelectorAll('[data-stat]').forEach(function(el) {
      el.textContent = stats[el.dataset.stat].toLocaleString('en-US');
    });

    buttons.forEach(function(button) {
      const count = countById[button.dataset.s2Paper];
      if (count === undefined) {
        return;
      }
      button.querySelector('.citation-count').textContent = count.toLocaleString('en-US');
      button.querySelector('.citation-label').textContent = count === 1 ? 'citation' : 'citations';
    });
  }

  // Storage can throw in private windows or when site data is blocked, so it is best-effort.
  try {
    const cached = JSON.parse(localStorage.getItem(cacheKey));
    if (cached && Date.now() - cached.time < cacheMs) {
      render(cached.papers);
      return;
    }
  } catch (e) {}

  fetch(apiUrl)
    .then(function(response) {
      if (!response.ok) {
        throw new Error('Semantic Scholar returned ' + response.status);
      }
      return response.json();
    })
    .then(function(data) {
      render(data.papers);
      try {
        localStorage.setItem(cacheKey, JSON.stringify({ time: Date.now(), papers: data.papers }));
      } catch (e) {}
    })
    .catch(function() {});
});
