// ── Quiz Game Logic ────────────────────────────────
let allCountries = [];
let quizQuestions = [];
let currentQuestionIndex = 0;
let score = 0;
let wrongQuestions = [];

const TOTAL_QUESTIONS = 20;

// OGP/version query string matching main app
const SVG_VERSION = 'v=20260415d';

// Elements
const screenStart = document.getElementById('screen-start');
const screenPlay = document.getElementById('screen-play');
const screenResult = document.getElementById('screen-result');

const startBtn = document.getElementById('start-btn');
const nextBtn = document.getElementById('next-btn');
const restartBtn = document.getElementById('restart-btn');

const questionFlag = document.getElementById('question-flag');
const optionsContainer = document.getElementById('options-container');
const explanationPanel = document.getElementById('explanation-panel');
const explanationTitle = document.getElementById('explanation-title');
const explanationDetails = document.getElementById('explanation-details');

const currentQuestionNumEl = document.getElementById('current-question-num');
const currentScoreEl = document.getElementById('current-score');
const progressBar = document.getElementById('progress-bar');

const resultEmoji = document.getElementById('result-emoji');
const finalScoreEl = document.getElementById('final-score');
const finalRankEl = document.getElementById('final-rank');
const finalMessageEl = document.getElementById('final-message');
const reviewSection = document.getElementById('review-section');
const reviewList = document.getElementById('review-list');

// 本土と国旗が同じ非独立地域を除外するためのコード一覧
// GP: グアドループ (フランス)
// RE: レユニオン (フランス)
// YT: マヨット (フランス)
// GF: 仏領ギアナ (フランス)
// MF: サン・マルタン (フランス)
// UM: 合衆国領有小離島 (アメリカ)
// BV: ブーベ島 (ノルウェー)
// SJ: スヴァールバル・ヤンマイエン (ノルウェー)
// HM: ハード・マクドナルド (オーストラリア)
const EXCLUDED_TERRITORIES = ['GP', 'RE', 'YT', 'GF', 'MF', 'UM', 'BV', 'SJ', 'HM'];

// ── Load Data ──────────────────────────────────────
async function initQuiz() {
  try {
    const response = await fetch('countries_data.json');
    const data = await response.json();
    
    // 本土と国旗が同じ非独立地域をフィルタリング
    allCountries = data.filter(c => !EXCLUDED_TERRITORIES.includes(c.code));
    
    // Enable start button after data is loaded
    startBtn.disabled = false;
  } catch (error) {
    console.error('Failed to load countries data:', error);
    alert('クイズデータの読み込みに失敗しました。ページを再読み込みしてください。');
  }
}

// ── Helper: Shuffle Array ──────────────────────────
function shuffle(array) {
  const arr = [...array];
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

// ── Start Game ─────────────────────────────────────
function startQuiz() {
  // Reset states
  score = 0;
  currentQuestionIndex = 0;
  wrongQuestions = [];
  
  currentScoreEl.textContent = '0';
  
  // Select 20 random countries
  const shuffledCountries = shuffle(allCountries);
  quizQuestions = shuffledCountries.slice(0, TOTAL_QUESTIONS);
  
  // Switch screen
  screenStart.classList.remove('active');
  screenResult.classList.remove('active');
  screenPlay.classList.add('active');
  
  showQuestion();
}

// ── Show Question ──────────────────────────────────
function showQuestion() {
  const currentQuestion = quizQuestions[currentQuestionIndex];
  
  // Update progress
  currentQuestionNumEl.textContent = currentQuestionIndex + 1;
  const progressPercent = (currentQuestionIndex / TOTAL_QUESTIONS) * 100;
  progressBar.style.width = `${progressPercent}%`;
  
  // Setup flag image
  questionFlag.src = `03_svg_verified/${currentQuestion.code}.svg?${SVG_VERSION}`;
  questionFlag.alt = `${currentQuestion.name_ja}の国旗`;
  
  // Generate options (1 correct, 3 wrong)
  let wrongCandidates = allCountries.filter(c => c.code !== currentQuestion.code);
  wrongCandidates = shuffle(wrongCandidates).slice(0, 3);
  
  const options = shuffle([currentQuestion, ...wrongCandidates]);
  
  // Render option buttons
  optionsContainer.innerHTML = '';
  options.forEach((opt, idx) => {
    const btn = document.createElement('button');
    btn.className = 'option-btn';
    btn.innerHTML = `${opt.name_ja} <span class="badge">${String.fromCharCode(65 + idx)}</span>`;
    btn.onclick = () => selectOption(btn, opt.code === currentQuestion.code, opt.name_ja);
    optionsContainer.appendChild(btn);
  });
  
  // Reset panel & buttons
  explanationPanel.classList.remove('active');
  nextBtn.style.display = 'none';
}

// ── Select Option ──────────────────────────────────
function selectOption(selectedBtn, isCorrect, selectedName) {
  const currentQuestion = quizQuestions[currentQuestionIndex];
  
  // Disable all options
  const optionButtons = optionsContainer.querySelectorAll('.option-btn');
  optionButtons.forEach(btn => {
    btn.classList.add('disabled');
  });
  
  // Update selected button state
  if (isCorrect) {
    selectedBtn.classList.add('correct');
    score++;
    currentScoreEl.textContent = score * 5; // Update dynamic score (5 pts each)
    
    explanationTitle.className = 'explanation-header success';
    explanationTitle.textContent = '正解！ 🎉';
  } else {
    selectedBtn.classList.add('wrong');
    explanationTitle.className = 'explanation-header danger';
    explanationTitle.textContent = '残念！ 😢';
    
    // Save to review list
    wrongQuestions.push({
      question: currentQuestion,
      yourAnswer: selectedName
    });
    
    // Highlight correct button
    optionButtons.forEach(btn => {
      if (btn.innerText.startsWith(currentQuestion.name_ja)) {
        btn.classList.remove('disabled');
        btn.classList.add('correct');
      }
    });
  }
  
  // Fill explanation panel
  const formalName = currentQuestion.formal_ja || currentQuestion.name_ja;
  const capital = currentQuestion.capital || '（データなし）';
  const region = currentQuestion.mofa_region || currentQuestion.region;
  
  explanationDetails.innerHTML = `
    <strong>正式国名:</strong> ${formalName}<br>
    <strong>首都:</strong> ${capital}<br>
    <strong>地域:</strong> ${region}
  `;
  
  explanationPanel.classList.add('active');
  nextBtn.style.display = 'block';
}

// ── Next Question ──────────────────────────────────
function nextQuestion() {
  currentQuestionIndex++;
  
  if (currentQuestionIndex < TOTAL_QUESTIONS) {
    showQuestion();
  } else {
    showResults();
  }
}

// ── Show Results ───────────────────────────────────
function showResults() {
  // Update progress bar to 100%
  progressBar.style.width = '100%';
  
  // Switch screen
  screenPlay.classList.remove('active');
  screenResult.classList.add('active');
  
  const finalScore = score * 5;
  finalScoreEl.textContent = `${finalScore}点`;
  
  // Rank and message based on score
  let rank = '';
  let emoji = '🏆';
  let message = '';
  
  if (finalScore === 100) {
    rank = '👑 国旗マスター (Perfect!)';
    emoji = '👑';
    message = '全問正解です！あなたは完璧な国旗の達人です！すべての国旗の色と国名を完璧に把握しています。';
    triggerConfetti();
  } else if (finalScore >= 85) {
    rank = '🎓 国旗エキスパート';
    emoji = '🎓';
    message = `素晴らしい成績です！20問中 ${score} 問正解しました。世界の国旗にかなり精通していますね。`;
    triggerConfetti();
  } else if (finalScore >= 60) {
    rank = '🚩 国旗愛好家';
    emoji = '🚩';
    message = `なかなかの実力です！20問中 ${score} 問正解しました。もう少しでエキスパートの仲間入りです。`;
  } else {
    rank = '🔰 ビギナー';
    emoji = '🔰';
    message = `クイズに挑戦していただきありがとうございます！20問中 ${score} 問正解しました。アトラスやガイドで復習して、もう一度満点を目指して挑戦してみましょう！`;
  }
  
  resultEmoji.textContent = emoji;
  finalRankEl.textContent = rank;
  finalMessageEl.textContent = message;
  
  // Render review list if there are wrong answers
  if (wrongQuestions.length > 0) {
    reviewList.innerHTML = '';
    wrongQuestions.forEach(item => {
      const q = item.question;
      
      const card = document.createElement('div');
      card.className = 'review-card';
      card.onclick = () => {
        alert(`${q.name_ja} (${q.formal_ja || q.name_ja})\n首都: ${q.capital || 'なし'}\n地域: ${q.mofa_region || q.region}`);
      };
      
      card.innerHTML = `
        <div class="review-flag">
          <img src="03_svg_verified/${q.code}.svg?${SVG_VERSION}" alt="${q.name_ja}">
        </div>
        <div class="review-info">
          <div class="review-country-name">${q.name_ja}</div>
          <div class="review-answers">
            あなたの回答: <span class="review-your-answer">${item.yourAnswer}</span><br>
            正解: <span class="review-correct-answer">${q.name_ja}</span>
          </div>
        </div>
      `;
      reviewList.appendChild(card);
    });
    reviewSection.style.display = 'block';
  } else {
    reviewSection.style.display = 'none';
  }
}

// ── Confetti Celebration ───────────────────────────
function triggerConfetti() {
  if (typeof confetti === 'function') {
    // Left-side burst
    confetti({
      particleCount: 80,
      angle: 60,
      spread: 55,
      origin: { x: 0, y: 0.8 }
    });
    // Right-side burst
    confetti({
      particleCount: 80,
      angle: 120,
      spread: 55,
      origin: { x: 1, y: 0.8 }
    });
    
    // Extra sparkles
    setTimeout(() => {
      confetti({
        particleCount: 50,
        spread: 100,
        origin: { x: 0.5, y: 0.4 }
      });
    }, 400);
  }
}

// ── Event Listeners ──────────────────────────────
startBtn.addEventListener('click', startQuiz);
nextBtn.addEventListener('click', nextQuestion);
restartBtn.addEventListener('click', startQuiz);

// ── Init ─────────────────────────────────────────
initQuiz();
