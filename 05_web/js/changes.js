/**
 * 国旗の変遷 2016–2026 — タイムラインデータ & レンダリング
 *
 * 各エントリの出典:
 *   - 検証済み indesign_data_merge.csv (Notes フィールド)
 *   - 各国政府公式発表・国連記録・Album des Pavillons
 */
(function () {
  'use strict';

  // SVG paths
  function svg(code) { return `03_svg_verified/${code}.svg`; }
  function wikiSvg(code) { return `01_svg_wikipedia/${code.toLowerCase()}.svg`; }

  /**
   * タイムラインデータ（年降順）
   *
   * type: 'new'=新国旗採用, 'modify'=デザイン修正, 'revert'=旧デザイン復帰,
   *       'defacto'=事実上の変更, 'reject'=変更否決, 'color'=色規格変更
   */
  const CHANGES = [
    // ── 2026 ──
    {
      year: 2026,
      code: 'HN',
      name_ja: 'ホンジュラス',
      name_en: 'Honduras',
      type: 'revert',
      typeLabel: '復帰',
      date: '2026年1月',
      description:
        '2022年にカストロ政権がターコイズブルーに変更した国旗の色を、' +
        '<strong>伝統的な濃紺（ネイビーブルー）に戻す</strong>ことを決定。' +
        '1949年の立法令が定めた色調を巡り、政権ごとに揺れ動いた青の歴史に、ひとまず決着がついた。'
    },
    // ── 2025 ──
    {
      year: 2025,
      code: 'SY',
      name_ja: 'シリア',
      name_en: 'Syria',
      type: 'new',
      typeLabel: '新国旗',
      date: '2025年4月（国連掲揚）',
      description:
        '2024年12月のアサド政権崩壊に伴い、旧来の赤白黒二つ星旗から' +
        '<strong>「独立旗」（緑・白・黒に赤三つ星）</strong>に変更。' +
        '内戦中に反体制派が掲げてきたこの旗が正式に国旗となり、' +
        '2025年4月には国連本部でも新旗が掲揚された。'
    },
    // ── 2023 ──
    {
      year: 2023,
      code: 'KG',
      name_ja: 'キルギス',
      name_en: 'Kyrgyzstan',
      type: 'modify',
      typeLabel: 'デザイン修正',
      date: '2023年12月26日施行',
      description:
        '中央の<strong>テュンデュク（遊牧民の天幕ユルトの天窓）の太陽光線を波線から直線に変更</strong>。' +
        'ジャパロフ大統領が「波線だとヒマワリに見える」と指摘したことがきっかけ。' +
        '2023年12月22日署名、26日施行。赤地に金色の太陽という基本デザインは維持。'
    },
    {
      year: 2023,
      code: 'MQ',
      name_ja: 'マルティニーク',
      name_en: 'Martinique',
      type: 'new',
      typeLabel: '新旗採択',
      date: '2023年2月2日',
      description:
        'フランス海外地域圏マルティニークが、スポーツ・文化イベント用の<strong>公式地域旗を初採択</strong>。' +
        '旗竿側に赤い三角、上段が緑、下段が黒のパン=アフリカン・カラーを採用。' +
        'これまで独自の公式旗を持たなかった同地域の歴史的な一歩。' +
        'ただし法的にはフランス三色旗が引き続き正式な国旗。'
    },
    // ── 2022 ──
    {
      year: 2022,
      code: 'HN',
      name_ja: 'ホンジュラス',
      name_en: 'Honduras',
      type: 'color',
      typeLabel: '色変更',
      date: '2022年1月',
      description:
        'カストロ新政権が国旗の青を<strong>ターコイズブルー（セルレアン）に変更</strong>。' +
        '1949年の立法令が定めた「歴史的な青」への回帰を標榜したが、' +
        '長年馴染んだ濃紺からの変更には賛否両論が巻き起こった。' +
        '結局この変更は2026年1月に撤回されることになる。'
    },
    // ── 2021 ──
    {
      year: 2021,
      code: 'AF',
      name_ja: 'アフガニスタン',
      name_en: 'Afghanistan',
      type: 'defacto',
      typeLabel: '事実上の変更',
      date: '2021年8月15日〜',
      description:
        'タリバンがカブールを制圧し「アフガニスタン・イスラム首長国」を宣言。' +
        '国際的に承認された黒・赤・緑の三色旗に代わり、' +
        '<strong>白地に黒のシャハーダ（信仰告白）</strong>を掲げた。' +
        '国際社会では三色旗が依然として正統な国旗とみなされているが、' +
        '国内では事実上タリバンの白旗が使用されている。'
    },
    // ── 2017 ──
    {
      year: 2017,
      code: 'MR',
      name_ja: 'モーリタニア',
      name_en: 'Mauritania',
      type: 'modify',
      typeLabel: 'デザイン修正',
      date: '2017年8月5日国民投票、10月施行',
      description:
        '国民投票により、従来の緑地に黄色の三日月と星のデザインに' +
        '<strong>上下2本の赤い帯を追加</strong>。' +
        '赤はフランスからの独立闘争で流された血を象徴する。' +
        '赤帯の幅はそれぞれ旗の高さの1/5。2020年に正式なグラフィックガイドラインが公表された。'
    },
    // ── 2016 ──
    {
      year: 2016,
      code: 'NZ',
      name_ja: 'ニュージーランド',
      name_en: 'New Zealand',
      type: 'reject',
      typeLabel: '変更否決',
      date: '2016年3月（国民投票）',
      description:
        '2段階の国民投票で国旗変更の是非を問うも、<strong>56.7%が現行デザインを支持</strong>して否決。' +
        '銀シダ（シルバーファーン）の新デザイン案は健闘したが、' +
        '親しんだユニオンジャック付きブルーエンサインへの愛着が勝った。' +
        '変更には至らなかったが、国旗デザインについて国民的な議論が行われた希有な事例。'
    },
  ];

  // ── Render ──
  const container = document.getElementById('timeline');
  let html = '';
  let currentYear = null;
  let animIndex = 0;

  CHANGES.forEach((c) => {
    // Year marker
    if (c.year !== currentYear) {
      currentYear = c.year;
      html += `
      <div class="year-marker" style="animation-delay:${animIndex * 80}ms">
        <div class="year-dot"></div>
        <div class="year-label">${c.year}</div>
      </div>`;
      animIndex++;
    }

    // Badge class
    const badgeClass = {
      'new': 'badge-new',
      'modify': 'badge-modify',
      'revert': 'badge-revert',
      'defacto': 'badge-defacto',
      'reject': 'badge-reject',
      'color': 'badge-color',
    }[c.type] || '';

    // Flag display — current verified SVG
    const currentFlag = `<img src="${svg(c.code)}" alt="${c.code}" onerror="this.src='${wikiSvg(c.code)}'">`;

    html += `
    <div class="change-card" style="animation-delay:${animIndex * 80}ms">
      <div class="change-dot"></div>
      <div class="change-body">
        <div class="change-header">
          <div class="flag-compare">
            ${currentFlag}
            <div class="flag-label">現行旗</div>
          </div>
          <div class="change-info">
            <div class="change-country">
              <span class="change-country-name">${c.name_ja}</span>
              <span class="change-country-en">${c.name_en}</span>
              <span class="change-type-badge ${badgeClass}">${c.typeLabel}</span>
            </div>
            <div class="change-date">📅 ${c.date}</div>
            <p class="change-description">${c.description}</p>
          </div>
        </div>
      </div>
    </div>`;
    animIndex++;
  });

  container.innerHTML = html;

})();
