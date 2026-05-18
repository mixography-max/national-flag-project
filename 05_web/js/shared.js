/**
 * Shared UI — Hero sparkles & nav scroll behavior
 * Loaded on every page of the Flag Atlas site.
 */
(function () {
  'use strict';

  // ── Hero Sparkles ─────────────────────────────
  const sparkleContainer = document.getElementById('hero-sparkles');
  if (sparkleContainer) {
    const COLORS = ['gold', 'purple', 'teal', 'white'];
    const COUNT = 24;
    for (let i = 0; i < COUNT; i++) {
      const s = document.createElement('div');
      s.className = 'sparkle ' + COLORS[i % COLORS.length];
      s.style.left = Math.random() * 100 + '%';
      s.style.top  = Math.random() * 100 + '%';
      s.style.animationDelay    = (Math.random() * 5).toFixed(2) + 's';
      s.style.animationDuration = (3.5 + Math.random() * 2.5).toFixed(2) + 's';
      sparkleContainer.appendChild(s);
    }
  }

  // ── Nav scroll shadow ─────────────────────────
  const nav = document.getElementById('site-nav');
  if (nav) {
    let ticking = false;
    window.addEventListener('scroll', function () {
      if (!ticking) {
        requestAnimationFrame(function () {
          if (window.scrollY > 10) {
            nav.classList.add('scrolled');
          } else {
            nav.classList.remove('scrolled');
          }
          ticking = false;
        });
        ticking = true;
      }
    });
  }
})();
