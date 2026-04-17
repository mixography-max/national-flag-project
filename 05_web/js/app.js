// ── Phase 4 Data & State ──────────────────────────
let ALL_FLAGS = [];
let activeRegion = 'all';
let searchQuery = '';
let viewMode = 'normal';
let showVerified = true;
const SVG_VERSION = 'v=20260415d'; // 250/250 verified: SJ/TF/UM color data added

// Similar flag pairs for comparison
const SIMILAR_PAIRS = [
  { a: 'TD', b: 'RO', label: 'チャド vs ルーマニア (ほぼ同一の三色旗)' },
  { a: 'MC', b: 'ID', label: 'モナコ vs インドネシア (赤白二色/比率違い)' },
  { a: 'IE', b: 'CI', label: 'アイルランド vs コートジボワール (逆配色)' },
  { a: 'NL', b: 'LU', label: 'オランダ vs ルクセンブルク (青の濃さ)' },
  { a: 'AU', b: 'NZ', label: 'オーストラリア vs ニュージーランド' },
  { a: 'NO', b: 'IS', label: 'ノルウェー vs アイスランド (逆配色)' },
  { a: 'SN', b: 'ML', label: 'セネガル vs マリ (中央の星)' },
  { a: 'GN', b: 'ML', label: 'ギニア vs マリ (逆配色)' },
];

// ── Load Data ─────────────────────────────────────
async function loadData() {
  const resp = await fetch('flags_data.json');
  ALL_FLAGS = await resp.json();
  updateStats();
  renderGrid();
  renderSimilarPairs();
}

function updateStats() {
  document.getElementById('stat-total').textContent = ALL_FLAGS.length;
  const verifiedCount = ALL_FLAGS.filter(f => f.colors.length > 0).length;
  document.getElementById('stat-verified').textContent = verifiedCount;
  const totalColors = ALL_FLAGS.reduce((sum, f) => sum + f.colors.length, 0);
  document.getElementById('stat-colors').textContent = totalColors;
  const regions = new Set(ALL_FLAGS.map(f => f.region));
  document.getElementById('stat-regions').textContent = regions.size;
}

// ── Render Grid ───────────────────────────────────
function renderGrid() {
  const grid = document.getElementById('flag-grid');
  const filtered = ALL_FLAGS.filter(f => {
    if (activeRegion !== 'all' && f.region !== activeRegion) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return f.code.toLowerCase().includes(q)
        || f.name_en.toLowerCase().includes(q)
        || f.name_ja.includes(q)
        || f.region.toLowerCase().includes(q)
        || f.subregion.toLowerCase().includes(q);
    }
    return true;
  });

  if (filtered.length === 0) {
    grid.innerHTML = '<div class="no-results"><div class="icon">🏴</div><p>No flags found</p></div>';
    return;
  }

  grid.className = 'flag-grid' + (viewMode === 'compact' ? ' compact' : '');

  grid.innerHTML = filtered.map(f => {
    const svgDir = showVerified ? '03_svg_verified' : '01_svg_wikipedia';
    const badge = showVerified ? 'verified' : 'wiki';
    const badgeText = showVerified ? 'Verified' : 'Wiki';

    const colorDots = f.colors.slice(0, 8).map(c =>
      `<div class="color-dot" style="background:${c.hex}" title="${c.color_name}: ${c.hex}"></div>`
    ).join('');

    return `
      <div class="flag-card" data-code="${f.code}" onclick="openModal('${f.code}')">
        <div class="flag-img-wrap">
          <img src="${svgDir}/${f.code}.svg?${SVG_VERSION}" alt="${f.name_en}" loading="lazy"
               onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22300%22 height=%22200%22><rect fill=%22%23333%22 width=%22300%22 height=%22200%22/><text x=%22150%22 y=%22105%22 text-anchor=%22middle%22 fill=%22%23666%22 font-family=%22Inter%22 font-size=%2216%22>No SVG</text></svg>'">
          <span class="source-badge badge-${badge}">${badgeText}</span>
        </div>
        <div class="flag-info">
          <div class="flag-code">${f.code}</div>
          <div class="flag-name">${f.name_en}</div>
          <div class="flag-name-ja">${f.name_ja}</div>
          <div class="flag-meta">
            <span>${f.ratio || '—'}</span>
            <span>·</span>
            <span>${f.region}</span>
          </div>
          <div class="color-dots">${colorDots}</div>
        </div>
      </div>
    `;
  }).join('');
}

// ── Modal ────────────────────────────────────────
function openModal(code) {
  const f = ALL_FLAGS.find(x => x.code === code);
  if (!f) return;

  document.getElementById('modal-title').innerHTML = `
    <h2>${f.name_en} <span class="code-badge">${f.code}</span></h2>
    <p>${f.name_ja} — ${f.region} / ${f.subregion}</p>
  `;

  document.getElementById('modal-flag').innerHTML = `
    <div class="modal-flag-img">
      <div class="compare-toggle">
        <button class="active" onclick="switchModalView(this, '${f.code}', 'verified')">✅ Verified（公式色・法定比率）</button>
        <button onclick="switchModalView(this, '${f.code}', 'wiki')">📘 Wikipedia（Wikimedia Commons）</button>
      </div>
      <img id="modal-img" src="03_svg_verified/${f.code}.svg?${SVG_VERSION}" alt="${f.name_en}"
           onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22300%22 height=%22200%22><rect fill=%22%23333%22 width=%22300%22 height=%22200%22/><text x=%22150%22 y=%22105%22 text-anchor=%22middle%22 fill=%22%23666%22 font-size=%2214%22>N/A</text></svg>'">
    </div>
    <div class="modal-flag-details">
      <div class="detail-row"><span class="detail-label">Ratio</span><span class="detail-value">${f.ratio || '—'}</span></div>
      <div class="detail-row"><span class="detail-label">Status</span><span class="detail-value">${f.status || '—'}</span></div>
      <div class="detail-row"><span class="detail-label">Region</span><span class="detail-value">${f.region}</span></div>
      <div class="detail-row"><span class="detail-label">Subregion</span><span class="detail-value">${f.subregion}</span></div>
      <div class="detail-row"><span class="detail-label">Colors</span><span class="detail-value">${f.colors.length}</span></div>
    </div>
  `;

  if (f.colors.length > 0) {
    document.getElementById('modal-colors').innerHTML = `
      <h3>Color Specifications</h3>
      <table class="color-table">
        <thead>
          <tr><th>Color</th><th>HEX</th><th>Pantone</th><th>CMYK</th></tr>
        </thead>
        <tbody>
          ${f.colors.map(c => `
            <tr>
              <td><span class="color-swatch" style="background:${c.hex}"></span>${c.color_name}</td>
              <td><code>${c.hex}</code></td>
              <td>${c.pantone || '—'}</td>
              <td>${c.cmyk || '—'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } else {
    document.getElementById('modal-colors').innerHTML = '<p style="color:var(--text-muted);padding:0 1.5rem">No color data available</p>';
  }

  // Handle Notes mapping for Phase 4
  const notesEl = document.getElementById('modal-notes');
  const notesText = document.getElementById('modal-notes-text');
  if (f.notes && f.notes.trim()) {
    // Basic text to HTML conversion
    notesText.innerHTML = f.notes.replace(/\n/g, '<br>');
    notesEl.style.display = 'block';
  } else {
    notesEl.style.display = 'none';
  }

  // Handle source
  document.getElementById('modal-source').innerHTML = f.specs_source
    ? `<strong>Source/De Jure:</strong> ${f.specs_source}`
    : '';

  // Handle download button logic
  const downloadBtn = document.getElementById('download-btn');
  downloadBtn.onclick = () => {
    const a = document.createElement('a');
    a.href = `03_svg_verified/${f.code}.svg?${SVG_VERSION}`;
    a.download = `Flag_of_${f.name_en.replace(/ /g, '_')}_Verified.svg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  document.getElementById('modal-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function switchModalView(btn, code, view) {
  const buttons = btn.parentElement.querySelectorAll('button');
  buttons.forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const img = document.getElementById('modal-img');
  img.src = view === 'verified'
    ? `03_svg_verified/${code}.svg?${SVG_VERSION}`
    : `01_svg_wikipedia/${code}.svg?${SVG_VERSION}`;
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
  document.body.style.overflow = '';
}

// ── Similar Pairs ────────────────────────────────
function renderSimilarPairs() {
  const container = document.getElementById('similar-pairs');
  container.innerHTML = SIMILAR_PAIRS.map(pair => {
    const a = ALL_FLAGS.find(f => f.code === pair.a);
    const b = ALL_FLAGS.find(f => f.code === pair.b);
    if (!a || !b) return '';
    return `
      <div class="pair-card">
        <div class="pair-flag" onclick="openModal('${a.code}')" style="cursor:pointer">
          <img src="03_svg_verified/${a.code}.svg?${SVG_VERSION}" alt="${a.name_en}" loading="lazy">
        </div>
        <div style="text-align:center">
          <div class="pair-vs">VS</div>
          <div class="pair-info">${pair.label}</div>
        </div>
        <div class="pair-flag" onclick="openModal('${b.code}')" style="cursor:pointer">
          <img src="03_svg_verified/${b.code}.svg?${SVG_VERSION}" alt="${b.name_en}" loading="lazy">
        </div>
      </div>
    `;
  }).join('');
}

// ── Region Filtering Sync ────────────────────────
function setRegionFilter(region) {
  // Update Buttons
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  const btn = Array.from(document.querySelectorAll('.filter-btn')).find(b => b.dataset.region === region);
  if (btn) btn.classList.add('active');
  
  // Update Mini Map Config
  document.querySelectorAll('.map-node').forEach(n => n.classList.remove('active'));
  if (region !== 'all') {
    const node = document.querySelector(`.map-node[data-region="${region}"]`);
    if (node) node.classList.add('active');
  }

  activeRegion = region;
  renderGrid();
}

// ── Event Listeners ──────────────────────────────
document.getElementById('search').addEventListener('input', e => {
  searchQuery = e.target.value;
  renderGrid();
});

document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => setRegionFilter(btn.dataset.region));
});

document.querySelectorAll('.map-node').forEach(node => {
  node.addEventListener('click', () => {
    // Toggle logic for clicking the same region
    const region = node.classList.contains('active') ? 'all' : node.dataset.region;
    setRegionFilter(region);
  });
});

document.querySelectorAll('.view-toggle button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.view-toggle button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    viewMode = btn.dataset.view;
    renderGrid();
  });
});

document.getElementById('modal-close').addEventListener('click', closeModal);
document.getElementById('modal-overlay').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

// ── Init ─────────────────────────────────────────
loadData();