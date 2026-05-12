/**
 * 国名・首都名一覧ページのJavaScript
 * - JSONデータの読み込み・テーブル表示
 * - 検索フィルタ（和文名・英文名・首都名）
 * - 地域フィルタ
 * - ソート機能
 */
(function () {
  'use strict';

  let allData = [];
  let filteredData = [];
  let currentRegion = 'all';
  let currentSort = { key: 'formal_ja', dir: 'asc' };
  let searchQuery = '';

  // ── DOM refs ──
  const tbody = document.getElementById('countries-tbody');
  const searchInput = document.getElementById('search-input');
  const regionFilters = document.getElementById('region-filters');
  const noResults = document.getElementById('no-results');
  const resultCount = document.getElementById('result-count');
  const statTotal = document.getElementById('stat-total');
  const statMofa = document.getElementById('stat-mofa');

  // ── Region mapping (CSV region → MOFA region) ──
  const CSV_TO_MOFA_REGION = {
    'Europe': '欧州',
    'Asia': 'アジア',
    'Africa': 'アフリカ',
    'Americas': '中南米',
    'Oceania': '大洋州',
    'Other': '',
  };

  // ── SVG path helper ──
  function flagSvgPath(code) {
    // Try verified first, fallback to wikipedia
    return `03_svg_verified/${code}.svg`;
  }

  function flagImgTag(code) {
    const src = flagSvgPath(code);
    const wikiSrc = `01_svg_wikipedia/${code.toLowerCase()}.svg`;
    return `<img class="flag-thumb" src="${src}" alt="${code}"
              onerror="this.onerror=null;this.src='${wikiSrc}';"
              loading="lazy">`;
  }

  // ── Determine effective region ──
  function getEffectiveRegion(item) {
    if (item.mofa_region) return item.mofa_region;
    // Fallback: guess from CSV region
    const csvRegion = item.region || '';
    if (csvRegion === 'Americas') {
      // Check if North America
      if (['US', 'CA'].includes(item.code)) return '北米';
      return '中南米';
    }
    if (csvRegion === 'Asia') {
      // Rough Middle East detection
      const middleEast = ['AF','AE','YE','IL','IQ','IR','OM','QA','KW','SA','SY','TR','BH','JO','LB','PS','CY'];
      if (middleEast.includes(item.code)) return '中東';
      return 'アジア';
    }
    return CSV_TO_MOFA_REGION[csvRegion] || '';
  }

  // ── Render table ──
  function render() {
    const rows = [];
    filteredData.forEach((item, i) => {
      const region = getEffectiveRegion(item);
      const hasMofa = item.has_mofa;
      const cls = hasMofa ? '' : 'no-mofa';

      rows.push(`<tr class="${cls}" style="animation-delay:${Math.min(i * 8, 400)}ms">
        <td class="td-flag">${flagImgTag(item.code)}</td>
        <td class="td-name-ja">${item.formal_ja || item.name_ja || '—'}</td>
        <td class="td-name-en">${item.formal_en || item.name_en || '—'}</td>
        <td class="td-capital">${item.capital || '—'}</td>
        <td class="td-note">${item.capital_note || ''}</td>
        <td><span class="region-badge" data-region="${region}">${region || '—'}</span></td>
      </tr>`);
    });

    tbody.innerHTML = rows.join('');
    noResults.style.display = filteredData.length === 0 ? 'block' : 'none';
    resultCount.textContent = `${filteredData.length} / ${allData.length} カ国・地域を表示`;
  }

  // ── Filter & Sort ──
  function applyFilters() {
    const q = searchQuery.toLowerCase();

    filteredData = allData.filter(item => {
      // Region filter
      if (currentRegion !== 'all') {
        const r = getEffectiveRegion(item);
        if (r !== currentRegion) return false;
      }

      // Search filter
      if (q) {
        const fields = [
          item.formal_ja, item.formal_en, item.name_ja, item.name_en,
          item.capital, item.capital_note, item.code
        ].map(s => (s || '').toLowerCase());
        if (!fields.some(f => f.includes(q))) return false;
      }

      return true;
    });

    // Sort
    const { key, dir } = currentSort;
    const mult = dir === 'asc' ? 1 : -1;
    filteredData.sort((a, b) => {
      const va = (a[key] || a.name_ja || '').toLowerCase();
      const vb = (b[key] || b.name_ja || '').toLowerCase();
      return va < vb ? -1 * mult : va > vb ? 1 * mult : 0;
    });

    render();
  }

  // ── Event: Search ──
  let searchTimer;
  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      searchQuery = searchInput.value.trim();
      applyFilters();
    }, 150);
  });

  // ── Event: Region filter ──
  regionFilters.addEventListener('click', (e) => {
    const btn = e.target.closest('.filter-btn');
    if (!btn) return;
    regionFilters.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentRegion = btn.dataset.region;
    applyFilters();
  });

  // ── Event: Sort ──
  document.querySelectorAll('.countries-table th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      if (currentSort.key === key) {
        currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc';
      } else {
        currentSort = { key, dir: 'asc' };
      }

      // Update UI
      document.querySelectorAll('.countries-table th').forEach(h => {
        h.classList.remove('sort-asc', 'sort-desc');
      });
      th.classList.add(currentSort.dir === 'asc' ? 'sort-asc' : 'sort-desc');

      applyFilters();
    });
  });

  // ── Load data ──
  fetch('countries_data.json')
    .then(r => r.json())
    .then(data => {
      allData = data;
      statTotal.textContent = data.length;
      statMofa.textContent = data.filter(d => d.has_mofa).length;
      applyFilters();
    })
    .catch(err => {
      console.error('Failed to load countries data:', err);
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:2rem;color:var(--text-muted)">データの読み込みに失敗しました</td></tr>';
    });

})();
