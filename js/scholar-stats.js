// Fills in the per-paper citation buttons and the sidebar citation stats from
// data/citations.json. That file is rebuilt daily by scripts/update_citations.py (run from a
// GitHub Action), which merges the citing-paper lists of Google Scholar (when a SerpApi key is
// set), Semantic Scholar and OpenAlex and counts a citing paper found by several sources once.
//
// If the file cannot be loaded, the snapshot numbers written into the HTML stay as they are.
document.addEventListener('DOMContentLoaded', function() {
  const statsBox = document.getElementById('researchStats');
  if (!statsBox) {
    return;
  }

  function setCount(button, count) {
    if (!button || typeof count !== 'number') {
      return;
    }
    button.querySelector('.citation-count').textContent = count.toLocaleString('en-US');
    button.querySelector('.citation-label').textContent = count === 1 ? 'citation' : 'citations';
  }

  fetch('data/citations.json', { cache: 'no-cache' })
    .then(function(response) {
      if (!response.ok) {
        throw new Error('citations.json returned ' + response.status);
      }
      return response.json();
    })
    .then(function(data) {
      Object.keys(data.papers || {}).forEach(function(key) {
        const paper = data.papers[key];
        const item = document.getElementById(key);
        if (!item) {
          return;
        }
        setCount(item.querySelector('.citation-button[data-s2-paper]'), paper.s2);
        setCount(item.querySelector('.citation-button[data-oa-work]'), paper.oa);
        setCount(item.querySelector('.citation-button[data-gs]'), paper.gs);
      });

      statsBox.querySelectorAll('[data-stat]').forEach(function(el) {
        const value = data.totals && data.totals[el.dataset.stat];
        if (typeof value === 'number') {
          el.textContent = value.toLocaleString('en-US');
        }
      });
    })
    .catch(function() {});
});
