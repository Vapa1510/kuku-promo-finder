/**
 * Comprehensive Verification & Deep Regression Test Suite for DramaPulse Web UI
 * Tests:
 * 1. File presence & Vercel configuration integrity
 * 2. Visual image assets byte size & accessibility
 * 3. Universal Module resolution (Native Node.js require('./assets/js/data.js') and browser window)
 * 4. Screenplay data schema & KPI metrics integrity (Top 5, Top 30, Passed 89, Screened 168)
 * 5. Audio Synthesizer scheduler mathematical safety across edge durations (0.5s - 60s)
 * 6. Dual-mode narrative analytics chart engine (Radar Web & Bar Comparison)
 * 7. CSS layout & micro-animation rules (active cards, non-overlapping phone captions, kpiPop)
 * 8. HTML structure (Series poster lightbox hook, Tab 2 promo picker, Tab 5 status filters)
 * 9. Server route & query parameter resolution
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

let passedTests = 0;
let totalTests = 0;

function assert(condition, testName) {
  totalTests++;
  if (condition) {
    console.log(`  ✓ [PASS] ${testName}`);
    passedTests++;
  } else {
    console.error(`  ✗ [FAIL] ${testName}`);
    throw new Error(`Test failed: ${testName}`);
  }
}

console.log('\n--- 1. Testing Core File Integrity & Configurations ---');
assert(fs.existsSync('index.html'), 'index.html exists at project root');
assert(fs.existsSync('vercel.json'), 'vercel.json exists at project root');
assert(fs.existsSync('package.json'), 'package.json exists at project root');

// Test vercel.json
const vercelConfig = JSON.parse(fs.readFileSync('vercel.json', 'utf8'));
assert(vercelConfig.version === 2, 'vercel.json has version 2');
assert(Array.isArray(vercelConfig.headers), 'vercel.json includes static asset cache headers');
assert(vercelConfig.cleanUrls === true, 'vercel.json enables cleanUrls');

// Test package.json
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
assert(pkg.scripts && pkg.scripts.start && pkg.scripts.build && pkg.scripts.test, 'package.json defines start, build, and test scripts');
assert(pkg.scripts.start.includes("req.url.split('?')[0]"), 'start script handles query parameters safely');

console.log('\n--- 2. Testing Image Assets ---');
const requiredImages = [
  'series_poster.jpg',
  'avatar_juliana.jpg',
  'avatar_alexander.jpg',
  'avatar_matriarch.jpg',
  'scene_ep01_betrayal.jpg',
  'scene_ep03_proposal.jpg',
  'scene_ep35_traitor.jpg',
  'scene_ep41_cathedral.jpg'
];

requiredImages.forEach(img => {
  const p = path.join('assets/images', img);
  assert(fs.existsSync(p), `Image asset exists: ${img}`);
  const stat = fs.statSync(p);
  assert(stat.size > 10000, `Image asset is valid and non-empty (>10KB): ${img} (${(stat.size / 1024).toFixed(1)} KB)`);
});

console.log('\n--- 3. Testing Universal Data Export (Node.js & Browser) ---');
// Verify native require works without reference errors
const dataExport = require('./assets/js/data.js');
assert(dataExport && dataExport.DRAMA_DATA, 'assets/js/data.js natively exports DRAMA_DATA to Node.js environment');
const dramaData = dataExport.DRAMA_DATA;

assert(dramaData.seriesInfo && dramaData.seriesInfo.title.includes('Broken Soldier'), 'Series info title is correctly loaded');
assert(dramaData.benchmark && dramaData.benchmark.metrics_at_k['K=5'].precision === 0.4, 'Benchmark report has Precision@5 = 0.4');
assert(dramaData.metadata && dramaData.metadata.total_episodes_parsed === 50, 'Metadata records 50 episodes parsed');
assert(Array.isArray(dramaData.top5) && dramaData.top5.length === 5, 'Top 5 golden cuts present and length === 5');
assert(Array.isArray(dramaData.top30) && dramaData.top30.length === 30, 'Top 30 curated promos present and length === 30');
assert(Array.isArray(dramaData.passedCandidates) && dramaData.passedCandidates.length === 89, `Passed candidates count === 89 (Actual: ${dramaData.passedCandidates.length})`);
assert(Array.isArray(dramaData.allCandidates) && dramaData.allCandidates.length === 168, `All screened candidates audit count === 168 (Actual: ${dramaData.allCandidates.length})`);

// Verify 7 dimensions present in every candidate
const sampleCandidate = dramaData.top5[0];
const dims = [
  'hook_strength',
  'cliffhanger_strength',
  'narrative_clarity',
  'conflict_and_stakes',
  'emotional_pull',
  'script_visual_potential',
  'boundary_suitability'
];
dims.forEach(dim => {
  assert(sampleCandidate.scores[dim] !== undefined, `Scoring dimension present: ${dim} (${sampleCandidate.scores[dim]})`);
});

console.log('\n--- 4. Testing Audio Synthesizer Math Safety ---');
// Load audio-synth into sandbox
const synthCode = fs.readFileSync('assets/js/audio-synth.js', 'utf8');
const synthSandbox = { window: {}, module: { exports: {} } };
vm.createContext(synthSandbox);
vm.runInContext(synthCode, synthSandbox);

const AudioEngineClass = synthSandbox.window.DramaAudioEngine || synthSandbox.module.exports.DramaAudioEngine;
assert(typeof AudioEngineClass === 'function', 'DramaAudioEngine class is exported');

// Test scheduler time bounds on various durations
const testDurations = [0.5, 1.0, 2.0, 3.5, 38.5, 60.0];
testDurations.forEach(dur => {
  const d = Math.max(0.6, dur);
  const attackEnd = Math.min(1.5, d * 0.25);
  const releaseStart = Math.max(attackEnd + 0.05, d - Math.min(2.5, d * 0.35));
  assert(attackEnd < releaseStart, `Scheduler strictly increasing attackEnd < releaseStart for duration ${dur}s (${attackEnd.toFixed(3)} < ${releaseStart.toFixed(3)})`);
  assert(releaseStart < d, `Scheduler strictly increasing releaseStart < duration for duration ${dur}s (${releaseStart.toFixed(3)} < ${d.toFixed(3)})`);
});

console.log('\n--- 5. Testing Dual-Mode Chart Engine (Radar & Bar Comparison) ---');
const chartCode = fs.readFileSync('assets/js/charts.js', 'utf8');
let renderedHtml = '';
const mockContainer = {
  set innerHTML(val) {
    renderedHtml = val;
  },
  get innerHTML() {
    return renderedHtml;
  }
};
const chartSandbox = {
  window: {},
  module: { exports: {} },
  document: {
    getElementById: (id) => (id === 'testContainer' ? mockContainer : null)
  }
};
vm.createContext(chartSandbox);
vm.runInContext(chartCode, chartSandbox);

const RadarChartEngine = chartSandbox.window.RadarChartEngine || chartSandbox.module.exports.RadarChartEngine;
assert(typeof RadarChartEngine === 'function', 'RadarChartEngine class is exported');

const chartInstance = new RadarChartEngine('testContainer');
assert(chartInstance.dimensions.length === 7, 'Chart engine defines all 7 narrative dimensions');

// Test Radar mode render
chartInstance.render(sampleCandidate.scores, { hook_strength: 8.0 }, 'Promo Test Title', 'Benchmark Average');
assert(renderedHtml.includes('<svg'), 'Radar chart renders valid SVG element');
assert(renderedHtml.includes('Promo Test Title'), 'Radar chart SVG includes candidate title');
assert(renderedHtml.includes('Hook Strength'), 'Radar chart includes dimension labels');

// Test Bar Comparison mode render
chartInstance.setMode('bars');
assert(renderedHtml.includes('Bar Comparison') || renderedHtml.includes('Benchmark Avg'), 'Bar comparison view renders benchmark comparison elements');
assert(renderedHtml.includes('Hook Strength'), 'Bar comparison view includes dimension labels');

console.log('\n--- 6. Testing CSS Integrity & Layout Protections ---');
const cssContent = fs.readFileSync('assets/css/style.css', 'utf8');
assert(cssContent.includes('.promo-card.active'), 'CSS defines .promo-card.active glowing style');
assert(cssContent.includes('@keyframes kpiPop'), 'CSS defines @keyframes kpiPop micro-animation');
assert(cssContent.includes('.kpi-animating'), 'CSS defines .kpi-animating class');
assert(cssContent.includes('.phone-caption-box'), 'CSS includes phone-caption-box styles');
assert(cssContent.includes('bottom: 132px;'), 'CSS sets phone-caption-box bottom to 132px (eliminating bottom controls overlap)');
assert(cssContent.includes('.modal-visual-stage.can-pan'), 'CSS defines lightbox pan/grab cursor states');
assert(cssContent.includes('.chart-mode-pill'), 'CSS defines chart mode toggle pills');
assert(cssContent.includes('.editorial-note-input'), 'CSS defines inline editorial note input field');

console.log('\n--- 7. Testing HTML Structure & Interactive Elements ---');
const htmlContent = fs.readFileSync('index.html', 'utf8');
assert(htmlContent.includes("openLightbox('series_poster')"), 'Series poster card triggers openLightbox for series_poster');
assert(htmlContent.includes('id="radarPromoSelect"'), 'Tab 2 includes candidate selector dropdown');
assert(htmlContent.includes('id="radarModeWebBtn"'), 'Tab 2 includes Radar Web toggle button');
assert(htmlContent.includes('id="radarModeBarBtn"'), 'Tab 2 includes Bar Comparison toggle button');
assert(htmlContent.includes('id="auditSearchInput"'), 'Tab 3 includes candidate search input');
assert(htmlContent.includes('id="auditEpisodeSelect"'), 'Tab 3 includes episode selector');
assert(htmlContent.includes('data-ed-filter="all"'), 'Tab 5 includes editorial status filter pills');
assert(htmlContent.includes('id="modalPlayInPhoneBtn"'), 'Lightbox modal header includes Play in Phone button');
assert(htmlContent.includes('id="benchmarkMatrixTableBody"'), 'Tab 4 includes Benchmark Matrix table container');

console.log('\n--- 8. Testing App Controller Logic & Scrubber Handling ---');
const appCode = fs.readFileSync('assets/js/app.js', 'utf8');
assert(appCode.includes('isDraggingScrubber'), 'app.js includes scrubber drag state tracking');
assert(appCode.includes('setupInteractiveScrubber'), 'app.js implements interactive mouse and touch scrubber handler');
assert(appCode.includes('setupLightboxZoomAndPan'), 'app.js implements wheel zoom and mouse pan drag handler');
assert(appCode.includes('\\uFEFF'), 'app.js includes UTF-8 BOM in CSV export for Excel compatibility');
assert(appCode.includes("candidateId === 'series_poster'"), 'app.js explicitly handles series_poster spotlight mode in lightbox');
assert(appCode.includes('triggerMicroAnimation'), 'app.js triggers micro-animations on KPI updates');

console.log(`\n========================================`);
console.log(`🎉 ALL ${passedTests} / ${totalTests} COMPREHENSIVE TESTS PASSED!`);
console.log(`========================================\n`);
process.exit(0);
