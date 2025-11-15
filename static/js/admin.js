// admin.js — small helper for admin interactions (keeps template clean)
document.addEventListener('DOMContentLoaded', function () {
  const statusFilter = document.getElementById('filter-status');
  const priorityFilter = document.getElementById('filter-priority');
  const claimsGrid = document.getElementById('claims-grid');

  function applyFilters() {
    const s = statusFilter ? statusFilter.value : 'all';
    const p = priorityFilter ? priorityFilter.value : 'all';
    if (!claimsGrid) return;
    const cards = claimsGrid.querySelectorAll('article.card');
    cards.forEach(c => {
      const cs = c.dataset.status || 'pending';
      const cp = c.dataset.priority || 'small';
      let show = true;
      if (s !== 'all' && cs !== s) show = false;
      if (p !== 'all' && cp !== p) show = false;
      c.style.display = show ? '' : 'none';
    });
  }

  if (statusFilter) statusFilter.addEventListener('change', applyFilters);
  if (priorityFilter) priorityFilter.addEventListener('change', applyFilters);

  // wire demo action buttons
  document.querySelectorAll('button[data-action]').forEach(btn => {
    btn.addEventListener('click', e => {
      const action = btn.dataset.action;
      if (action === 'view') {
        const tgt = btn.dataset.target;
        const el = document.querySelector(tgt);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } else {
        // Demo-only: show an informative toast/alert
        const name = (btn.closest('article') && btn.closest('article').querySelector('.muted')) ?
                     btn.closest('article').querySelector('.muted').innerText : '';
        alert('Demo action: ' + action + (name ? '\n' + name : ''));
      }
    });
  });
});
