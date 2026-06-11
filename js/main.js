/* ═══════════════════════════════════════════
   Serenity-A — Main JS
   ═══════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {

  // ── Single Page App: page navigation ──
  const pages = document.querySelectorAll('.page');
  const navLinks = document.querySelectorAll('.navbar-links a');
  const toggleBtn = document.querySelector('.navbar-toggle');
  const navLinksContainer = document.querySelector('.navbar-links');

  function showPage(pageId) {
    // Hide all pages
    pages.forEach(p => p.classList.remove('active'));
    // Show target
    const target = document.getElementById(pageId);
    if (target) target.classList.add('active');
    // Update nav
    navLinks.forEach(a => {
      a.classList.toggle('active', a.dataset.page === pageId);
    });
    // Close mobile menu
    if (navLinksContainer) navLinksContainer.classList.remove('open');
    // Update URL hash
    history.pushState(null, '', `#${pageId}`);
  }

  // Nav link clicks
  navLinks.forEach(a => {
    a.addEventListener('click', e => {
      e.preventDefault();
      showPage(a.dataset.page);
    });
  });

  // Mobile toggle
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      navLinksContainer.classList.toggle('open');
    });
  }

  // Initial page from hash or default
  const hash = location.hash.slice(1) || 'index';
  showPage(hash);

  // Handle back/forward
  window.addEventListener('popstate', () => {
    const h = location.hash.slice(1) || 'index';
    showPage(h);
  });

  // ── Scrollspy for page-internal anchors ──
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const href = a.getAttribute('href');
      // Only handle page-internal anchors (not page switches)
      if (href === '#') return;
      const el = document.querySelector(href);
      if (el) {
        e.preventDefault();
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // ── Copy code buttons (optional enhancement) ──
  document.querySelectorAll('pre').forEach(block => {
    const btn = document.createElement('button');
    btn.textContent = '📋';
    btn.style.cssText = 'position:absolute;top:8px;right:8px;background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:4px 8px;cursor:pointer;font-size:12px;color:var(--text-dim);opacity:0;transition:opacity 0.2s;';
    block.style.position = 'relative';
    block.appendChild(btn);
    block.addEventListener('mouseenter', () => btn.style.opacity = '1');
    block.addEventListener('mouseleave', () => btn.style.opacity = '0');
    btn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(block.textContent.replace('📋', ''));
        btn.textContent = '✅';
        setTimeout(() => btn.textContent = '📋', 1500);
      } catch {}
    });
  });

});
