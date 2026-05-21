(function () {
  'use strict';

  // ── Global State ─────────────────────────────────
  let ALL_FLAGS = [];
  let currentFamily = 'red'; // デフォルトは赤
  let sortBy = 'popularity'; // デフォルトは人気順
  const SVG_VERSION = 'v=20260415d'; // 一貫したSVGキャッシュバスター

  // ── Color Family Definitions ──────────────────────
  const FAMILIES = {
    red: { name_ja: '赤系統', emoji: '🔴', benchmark: '186 C' },
    blue: { name_ja: '青系統', emoji: '🔵', benchmark: '280 C' },
    green: { name_ja: '緑系統', emoji: '🟢', benchmark: '348 C' },
    yellow: { name_ja: '黄・金系統', emoji: '🟡', benchmark: '116 C' },
    orange: { name_ja: '橙系統', emoji: '🟠', benchmark: '021 C' },
    brown: { name_ja: '茶系統', emoji: '🟤', benchmark: '725 C' },
    black: { name_ja: '黒系統', emoji: '⚫', benchmark: 'Black C' },
    white: { name_ja: '白系統', emoji: '⚪', benchmark: 'White' },
    others: { name_ja: 'その他 (紫等)', emoji: '🟣', benchmark: null }
  };

  // ベンチマーク色（標準色）の静的データ定義
  const BENCHMARKS = {
    '186 C': {
      pantone: '186 C',
      hex: '#C8102E',
      cmyk: '0, 100, 85, 6',
      rgb: '200, 16, 46',
      desc: 'アメリカ、イギリス、日本など、非常に多くの国旗で採用されている国際的に最も代表的な赤色です。強さ、勇気、または独立のために流された血を象徴することが多い色です。'
    },
    '280 C': {
      pantone: '280 C',
      hex: '#012169',
      cmyk: '100, 80, 0, 0',
      rgb: '1, 33, 105',
      desc: 'イギリスのユニオンジャックや、オーストラリア、ニュージーランドなど旧英国領の国旗に多く見られる「ダークネイビー（濃紺）」系統の標準色です。誠実、海、または大空を象徴します。'
    },
    '348 C': {
      pantone: '348 C',
      hex: '#00843D',
      cmyk: '96, 2, 100, 12',
      rgb: '0, 132, 61',
      desc: 'イタリア、メキシコ、アラブ首長国連邦などで採用されている、標準的で鮮やかな緑色です。豊かな大地や農業、希望、あるいはイスラム教を象徴します。'
    },
    '116 C': {
      pantone: '116 C',
      hex: '#FFCD00',
      cmyk: '0, 10, 98, 0',
      rgb: '255, 205, 0',
      desc: 'ドイツ、ベルギー、ウクライナ、ルーマニアなどで採用されている代表的な黄色（ゴールド）です。豊かな太陽光、天然資源、富、正義や輝かしい未来を象徴します。'
    },
    '021 C': {
      pantone: '021 C',
      hex: '#FF6600',
      cmyk: '0, 65, 100, 0',
      rgb: '255, 102, 0',
      desc: 'アイルランド国旗やアルメニア国旗などで象徴的に使われている鮮やかなオレンジ色です。友愛、協調、または歴史的な連帯を象徴します。'
    },
    '725 C': {
      pantone: '725 C',
      hex: '#7D4016',
      cmyk: '0, 68, 100, 53',
      rgb: '125, 64, 22',
      desc: 'アルゼンチン国旗の「5月の太陽」の顔の輪郭や影、アメリカ領サモアの羽毛などで使われている標準的な茶色です。先住民の遺産や大地、動植物を象徴します。'
    },
    'Black C': {
      pantone: 'Black C',
      hex: '#000000',
      cmyk: '0, 0, 0, 100',
      rgb: '0, 0, 0',
      desc: 'ドイツ、ベルギー、アンゴラ、ジャマイカ等で採用されている標準的な黒色です。力強さ、アフリカの大地や人々、あるいは過去の苦難や克服した歴史を象徴します。'
    },
    'White': {
      pantone: 'White',
      hex: '#FFFFFF',
      cmyk: '0, 0, 0, 0',
      rgb: '255, 255, 255',
      desc: '平和、純潔、正義、あるいは雪や氷を象徴する無彩色の白です。ほぼすべての国旗において、他のシンボルを引き立てるための基本色として広く用いられています。'
    }
  };

  // ── Helper: Color Utilities ──────────────────────
  function hexToRgb(hex) {
    const cleanHex = hex.replace('#', '');
    const num = parseInt(cleanHex, 16);
    return {
      r: (num >> 16) & 255,
      g: (num >> 8) & 255,
      b: num & 255
    };
  }

  function rgbToHsl(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    let h, s, l = (max + min) / 2;

    if (max === min) {
      h = s = 0; // achromatic
    } else {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      switch (max) {
        case r: h = (g - b) / d + (g < b ? 6 : 0); break;
        case g: h = (b - r) / d + 2; break;
        case b: h = (r - g) / d + 4; break;
      }
      h /= 6;
    }
    return {
      h: Math.round(h * 360),
      s: Math.round(s * 100),
      l: Math.round(l * 100)
    };
  }

  // カラーファミリーへのマッピングロジック
  function classifyColor(colorName, hex) {
    const name = colorName.toLowerCase();
    
    // 1. キーワード優先ルール
    if (name.includes('white') || name.includes('silver')) return 'white';
    if (name.includes('black') || name.includes('charcoal')) return 'black';
    if (name.includes('brown') || name.includes('bronze')) return 'brown';
    if (name.includes('beige') || name.includes('sand') || name.includes('gold') || name.includes('yellow') || name.includes('lemon')) {
      if (name.includes('gold') || name.includes('yellow') || name.includes('lemon')) return 'yellow';
      return 'brown'; // ベージュやサンドは茶系統へ
    }
    if (name.includes('orange') || name.includes('saffron')) return 'orange';
    if (name.includes('red') || name.includes('crimson') || name.includes('scarlet') || name.includes('maroon') || name.includes('burgundy')) return 'red';
    if (name.includes('blue') || name.includes('navy') || name.includes('sky') || name.includes('ultramarine') || name.includes('cobalt') || name.includes('teal')) {
      if (name.includes('teal')) return 'green'; // 鴨羽色は緑へ
      return 'blue';
    }
    if (name.includes('green') || name.includes('emerald') || name.includes('olive')) return 'green';
    if (name.includes('purple') || name.includes('violet') || name.includes('pink') || name.includes('magenta')) return 'others';

    // 2. HSLによる自動判定
    try {
      const rgb = hexToRgb(hex);
      const hsl = rgbToHsl(rgb.r, rgb.g, rgb.b);

      // 無彩色・極低彩度判定
      if (hsl.l >= 93 || (hsl.l >= 85 && hsl.s <= 8)) return 'white';
      if (hsl.l <= 12 || (hsl.l <= 20 && hsl.s <= 10)) return 'black';
      if (hsl.s <= 10) return 'others'; // 灰色はothersへ分類

      // 色相(Hue)による判定
      const h = hsl.h;
      if (h < 15 || h >= 345) {
        // 暗い赤は茶色に入ることがある
        return (hsl.l < 30) ? 'brown' : 'red';
      }
      if (h >= 15 && h < 45) {
        return (hsl.l < 35) ? 'brown' : 'orange';
      }
      if (h >= 45 && h < 70) return 'yellow';
      if (h >= 70 && h < 165) return 'green';
      if (h >= 165 && h < 255) return 'blue';
      return 'others'; // 紫・マゼンタなど
    } catch (e) {
      return 'others';
    }
  }

  // ── CIE76 色差 (Delta E) 計算ロジック ────────────────
  function rgbToXyz(r, g, b) {
    let rL = r / 255;
    let gL = g / 255;
    let bL = b / 255;

    rL = (rL > 0.04045) ? Math.pow((rL + 0.055) / 1.055, 2.4) : (rL / 12.92);
    gL = (gL > 0.04045) ? Math.pow((gL + 0.055) / 1.055, 2.4) : (gL / 12.92);
    bL = (bL > 0.04045) ? Math.pow((bL + 0.055) / 1.055, 2.4) : (bL / 12.92);

    rL *= 100;
    gL *= 100;
    bL *= 100;

    // D65 reference white 2° observer
    const x = rL * 0.4124 + gL * 0.3576 + bL * 0.1805;
    const y = rL * 0.2126 + gL * 0.7152 + bL * 0.0722;
    const z = rL * 0.0193 + gL * 0.1192 + bL * 0.9505;
    return { x, y, z };
  }

  function xyzToLab(x, y, z) {
    const xn = 95.047;
    const yn = 100.000;
    const zn = 108.883;

    let xL = x / xn;
    let yL = y / yn;
    let zL = z / zn;

    xL = (xL > 0.008856) ? Math.pow(xL, 1/3) : (7.787 * xL + 16 / 116);
    yL = (yL > 0.008856) ? Math.pow(yL, 1/3) : (7.787 * yL + 16 / 116);
    zL = (zL > 0.008856) ? Math.pow(zL, 1/3) : (7.787 * zL + 16 / 116);

    const l = (116 * yL) - 16;
    const a = 500 * (xL - yL);
    const bVal = 200 * (yL - zL);
    return { l, a, b: bVal };
  }

  function calculateDeltaE(hex1, hex2) {
    try {
      const rgb1 = hexToRgb(hex1);
      const rgb2 = hexToRgb(hex2);
      const xyz1 = rgbToXyz(rgb1.r, rgb1.g, rgb1.b);
      const xyz2 = rgbToXyz(rgb2.r, rgb2.g, rgb2.b);
      const lab1 = xyzToLab(xyz1.x, xyz1.y, xyz1.z);
      const lab2 = xyzToLab(xyz2.x, xyz2.y, xyz2.z);

      const dL = lab1.l - lab2.l;
      const da = lab1.a - lab2.a;
      const db = lab1.b - lab2.b;
      return Math.sqrt(dL * dL + da * da + db * db);
    } catch (e) {
      return 0;
    }
  }

  function getDeltaEDesc(de) {
    if (de < 1.0) return '区別困難';
    if (de < 3.0) return '極めて類似';
    if (de < 6.0) return '類似 (わずかな差)';
    if (de < 12.0) return '同系統 (明確な差)';
    return '異なるトーン';
  }

  // ── Load & Group Data ────────────────────────────
  async function loadData() {
    try {
      const resp = await fetch('flags_data.json');
      ALL_FLAGS = await resp.json();
      
      initTabs();
      renderPage();
      updateStats();
    } catch (err) {
      console.error('Failed to load flag data:', err);
    }
  }

  function updateStats() {
    // ユニークカラー数を測定
    const uniqueColors = new Set();
    ALL_FLAGS.forEach(f => {
      f.colors.forEach(c => {
        // Pantoneがある場合はPantoneを、無ければHEXをキーにする
        const key = (c.pantone && c.pantone.trim()) ? `pantone_${c.pantone.trim()}` : `hex_${c.hex}`;
        uniqueColors.add(key);
      });
    });
    document.getElementById('stat-total-colors').textContent = uniqueColors.size;
    
    // 最多使用のPantoneを調べる
    const pantoneCounts = {};
    ALL_FLAGS.forEach(f => {
      f.colors.forEach(c => {
        if (c.pantone && c.pantone.trim() && c.pantone.trim() !== 'White') {
          const name = c.pantone.trim();
          pantoneCounts[name] = (pantoneCounts[name] || 0) + 1;
        }
      });
    });
    
    let popularPantone = '—';
    let maxCount = 0;
    for (const [p, count] of Object.entries(pantoneCounts)) {
      if (count > maxCount) {
        maxCount = count;
        popularPantone = `${p} (${count}国)`;
      }
    }
    document.getElementById('stat-most-popular-pantone').textContent = popularPantone;
    document.getElementById('stat-color-families').textContent = Object.keys(FAMILIES).length;
  }

  // ── Init Tabs ────────────────────────────────────
  function initTabs() {
    const tabsContainer = document.getElementById('color-tabs');
    tabsContainer.innerHTML = Object.entries(FAMILIES).map(([key, f]) => {
      const activeClass = key === currentFamily ? 'active' : '';
      return `
        <button class="color-tab tab-${key} ${activeClass}" data-family="${key}">
          <span class="color-badge-dot"></span>
          ${f.emoji} ${f.name_ja}
        </button>
      `;
    }).join('');

    // イベントリスナー追加
    document.querySelectorAll('.color-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.color-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        currentFamily = tab.dataset.family;
        renderPage();
      });
    });

    // ソート切り替え
    document.getElementById('color-sort').addEventListener('change', (e) => {
      sortBy = e.target.value;
      renderPage();
    });
  }

  // ── Render Content ────────────────────────────────
  function renderPage() {
    // 1. カレントファミリーの色情報を集計
    const groups = {};
    
    ALL_FLAGS.forEach(f => {
      f.colors.forEach(c => {
        const family = classifyColor(c.color_name, c.hex);
        if (family !== currentFamily) return;

        // グループ化キー: Pantoneがある場合は正規化してキーに、無ければHEXをキーにする
        const hasPantone = c.pantone && c.pantone.trim();
        const key = hasPantone ? c.pantone.trim() : c.hex.toUpperCase();

        if (!groups[key]) {
          groups[key] = {
            key: key,
            pantone: hasPantone ? c.pantone.trim() : null,
            hex: c.hex,
            cmyk: c.cmyk || '—',
            rgb: c.rgb || '—',
            color_name: c.color_name,
            countries: []
          };
        }
        
        // 重複国登録を避ける
        if (!groups[key].countries.some(country => country.code === f.code)) {
          groups[key].countries.push({
            code: f.code,
            name_ja: f.name_ja,
            name_en: f.name_en
          });
        }
      });
    });

    // 2. ベンチマーク表示の構築
    renderBenchmark(groups);

    // 3. その他のバリエーションのソートと描画
    renderVariations(groups);
  }

  function renderBenchmark(groups) {
    const container = document.getElementById('benchmark-section');
    const familyInfo = FAMILIES[currentFamily];
    
    if (!familyInfo.benchmark || !BENCHMARKS[familyInfo.benchmark]) {
      container.style.display = 'none';
      return;
    }

    container.style.display = 'block';
    const bData = BENCHMARKS[familyInfo.benchmark];
    
    // このベンチマークキーがgroupsに含まれているかを調べる
    const activeGroup = groups[bData.pantone] || { countries: [] };
    
    // ベンチマークを国数表示用に更新
    const flagStripHtml = activeGroup.countries.map(c => `
      <div class="mini-flag-card" onclick="openModal('${c.code}')" title="${c.name_ja} (${c.name_en})">
        <div class="mini-flag-img">
          <img src="03_svg_verified/${c.code}.svg?${SVG_VERSION}" alt="${c.name_en}">
        </div>
        <div class="mini-flag-name">${c.name_ja}</div>
      </div>
    `).join('');

    container.innerHTML = `
      <div class="benchmark-card">
        <div class="benchmark-swatch-wrap">
          <div class="benchmark-swatch" style="background:${bData.hex}" onclick="copyToClipboard('${bData.hex}', 'HEX: ${bData.hex}')"></div>
        </div>
        <div class="benchmark-info">
          <span class="benchmark-badge">Standard Benchmark</span>
          <h2 class="benchmark-title">${familyInfo.emoji} 標準の${familyInfo.name_ja.replace('系統', '')} — Pantone ${bData.pantone}</h2>
          <p class="benchmark-desc">${bData.desc}</p>
          
          <div class="benchmark-meta">
            <div class="meta-item">
              <span class="meta-label">HEX</span>
              <span class="meta-value">${bData.hex}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">CMYK</span>
              <span class="meta-value">${bData.cmyk}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">RGB</span>
              <span class="meta-value">${bData.rgb}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">Used by</span>
              <span class="meta-value">${activeGroup.countries.length} カ国</span>
            </div>
          </div>

          ${activeGroup.countries.length > 0 ? `
            <div class="benchmark-countries-title">この色を使用している国々</div>
            <div class="flag-strip">${flagStripHtml}</div>
          ` : `
            <div class="benchmark-countries-title" style="color:var(--text-muted)">現在この色を使用している検証済み国旗はありません</div>
          `}
        </div>
      </div>
    `;
  }

  function renderVariations(groups) {
    const grid = document.getElementById('color-variation-grid');
    const familyInfo = FAMILIES[currentFamily];
    
    // ベンチマーク色は「その他のバリエーション」から除外する（ユーザー要望に沿う）
    const benchmarkKey = familyInfo.benchmark;
    const variationList = Object.values(groups).filter(g => g.key !== benchmarkKey);

    if (variationList.length === 0) {
      grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 2rem;">その他のバリエーションはありません。</div>';
      return;
    }

    // ソート処理
    if (sortBy === 'popularity') {
      // 使用国数が多い順
      variationList.sort((a, b) => b.countries.length - a.countries.length);
    } else if (sortBy === 'luminance') {
      // 輝度順 (RGB明度近似)
      variationList.sort((a, b) => {
        const rgbA = hexToRgb(a.hex);
        const rgbB = hexToRgb(b.hex);
        const lumA = 0.299 * rgbA.r + 0.587 * rgbA.g + 0.114 * rgbA.b;
        const lumB = 0.299 * rgbB.r + 0.587 * rgbB.g + 0.114 * rgbB.b;
        return lumB - lumA; // 明るい順
      });
    } else if (sortBy === 'pantone') {
      // Pantoneコード順（アルファベット昇順）
      variationList.sort((a, b) => {
        const keyA = a.pantone || a.hex;
        const keyB = b.pantone || b.hex;
        return keyA.localeCompare(keyB);
      });
    }

    const bData = familyInfo.benchmark ? BENCHMARKS[familyInfo.benchmark] : null;

    grid.innerHTML = variationList.map(g => {
      const colorTitle = g.pantone ? `Pantone ${g.pantone}` : `HEX ${g.hex}`;
      const subtitle = g.pantone ? `HEX ${g.hex}` : `CMYK: ${g.cmyk}`;
      
      // ベンチマークが存在する場合のみ知覚色差(Delta E)を計算して表示
      let deltaEHtml = '';
      if (bData) {
        const de = calculateDeltaE(bData.hex, g.hex);
        const desc = getDeltaEDesc(de);
        deltaEHtml = `
          <div class="color-card-delta-e" style="font-size:0.72rem; color:var(--text-muted); margin-top:0.25rem;">
            標準との知覚色差 (ΔE): <strong style="color:var(--accent); font-family:monospace;">${de.toFixed(1)}</strong> (${desc})
          </div>
        `;
      }

      const flagStripHtml = g.countries.map(c => `
        <div class="mini-flag-card" onclick="openModal('${c.code}')" title="${c.name_ja} (${c.name_en})">
          <div class="mini-flag-img">
            <img src="03_svg_verified/${c.code}.svg?${SVG_VERSION}" alt="${c.name_en}">
          </div>
          <div class="mini-flag-name">${c.name_ja}</div>
        </div>
      `).join('');

      return `
        <div class="color-card">
          <div class="color-card-top">
            <div class="color-card-swatch" style="background:${g.hex}" onclick="copyToClipboard('${g.hex}', '${colorTitle}')" title="Click to Copy HEX"></div>
            <div class="color-card-info">
              <div class="color-card-title">${colorTitle}</div>
              <div class="color-card-hex">${subtitle}</div>
              ${g.pantone ? `<div class="color-card-cmyk">CMYK: ${g.cmyk}</div>` : ''}
              ${deltaEHtml}
            </div>
          </div>
          <div class="color-card-countries">
            <div class="color-card-countries-label">使用国 (${g.countries.length})</div>
            <div class="flag-strip">${flagStripHtml}</div>
          </div>
        </div>
      `;
    }).join('');
  }

  // ── Clipboard Copy ────────────────────────────────
  window.copyToClipboard = function(text, label) {
    navigator.clipboard.writeText(text).then(() => {
      showToast(`コピーしました: ${label} (${text})`);
    }).catch(err => {
      console.error('Could not copy text: ', err);
    });
  };

  function showToast(message) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    container.appendChild(toast);
    
    // アニメーション完了後に要素を削除 (2.3秒後)
    setTimeout(() => {
      toast.remove();
    }, 2300);
  }

  // ── Modal UI Logic (Sync with app.js) ──────────────
  window.openModal = function(code) {
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

    const notesEl = document.getElementById('modal-notes');
    const notesText = document.getElementById('modal-notes-text');
    if (f.notes && f.notes.trim()) {
      notesText.innerHTML = f.notes.replace(/\n/g, '<br>');
      notesEl.style.display = 'block';
    } else {
      notesEl.style.display = 'none';
    }

    document.getElementById('modal-source').innerHTML = f.specs_source
      ? `<strong>Source/De Jure:</strong> ${f.specs_source}`
      : '';

    // Handle SVG download
    const svgBtn = document.getElementById('download-svg');
    svgBtn.onclick = () => {
      const a = document.createElement('a');
      a.href = `03_svg_verified/${f.code}.svg?${SVG_VERSION}`;
      a.download = `Flag_of_${f.name_en.replace(/ /g, '_')}_Verified.svg`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    };

    // Handle PNG download
    const pngBtn = document.getElementById('download-png');
    const pngFilename = f.name_en.replace(/ /g, '_');
    const pngPath = `png_flags/1080/${encodeURIComponent(pngFilename)}.png`;
    pngBtn.onclick = () => {
      const a = document.createElement('a');
      a.href = pngPath;
      a.download = `Flag_of_${pngFilename}_1080px.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    };

    // Handle AI download
    const aiBtn = document.getElementById('download-ai');
    aiBtn.onclick = () => {
      const a = document.createElement('a');
      a.href = `ai_cmyk/${f.code}.ai`;
      a.download = `Flag_of_${pngFilename}_CMYK.ai`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    };

    document.getElementById('modal-overlay').classList.add('open');
    document.body.style.overflow = 'hidden';
  };

  window.switchModalView = function(btn, code, view) {
    const buttons = btn.parentElement.querySelectorAll('button');
    buttons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const img = document.getElementById('modal-img');
    img.src = view === 'verified'
      ? `03_svg_verified/${code}.svg?${SVG_VERSION}`
      : `01_svg_wikipedia/${code}.svg?${SVG_VERSION}`;
  };

  function closeModal() {
    document.getElementById('modal-overlay').classList.remove('open');
    document.body.style.overflow = '';
  }

  // ── Init Event Listeners ──────────────────────────
  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
  });

  // ── Init ─────────────────────────────────────────
  loadData();
})();
