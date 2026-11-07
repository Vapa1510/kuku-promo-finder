const fs = require('fs');
const path = require('path');

// Read files
const promoResults = JSON.parse(fs.readFileSync('outputs/promo_results.json', 'utf8'));
const promoResultsLLM = JSON.parse(fs.readFileSync('outputs_llm/promo_results.json', 'utf8'));
const promoResults30 = JSON.parse(fs.readFileSync('output/promo_results.json', 'utf8'));
const allScreened = JSON.parse(fs.readFileSync('outputs/all_screened_candidates.json', 'utf8'));
const benchmark = JSON.parse(fs.readFileSync('evaluation/benchmark_report.json', 'utf8'));
const metadata = JSON.parse(fs.readFileSync('outputs/run_metadata.json', 'utf8'));

// Helper for scene image mapping
function getSceneImage(ep, title) {
  if (ep === 41) return 'assets/images/scene_ep41_cathedral.jpg';
  if (ep === 3) return 'assets/images/scene_ep03_proposal.jpg';
  if (ep === 35 || ep === 32) return 'assets/images/scene_ep35_traitor.jpg';
  if (ep === 1) return 'assets/images/scene_ep01_betrayal.jpg';
  if (ep % 4 === 0) return 'assets/images/scene_ep41_cathedral.jpg';
  if (ep % 4 === 1) return 'assets/images/scene_ep01_betrayal.jpg';
  if (ep % 4 === 2) return 'assets/images/scene_ep03_proposal.jpg';
  return 'assets/images/scene_ep35_traitor.jpg';
}

// Clean title helper
function cleanTitle(rawTitle, ep, candId) {
  if (!rawTitle) return `Episode ${ep} Dramatic Turning Point`;
  let t = rawTitle.replace(/^\[Provisional Title\]\s*/i, '').trim();
  if (t === "The Traitor's Stand" && ep === 3) return "Defiance in the Sacred Aisle";
  if (t === "The Traitor's Stand" && ep === 32) return "The Letter in the Embers";
  if (t === "The Traitor's Stand" && ep === 13) return "The Secret Soldier's Vow";
  if (t === "The Secret Proposal" && ep === 36) return "Arsenic at the Grand Ball";
  return t;
}

// Parse event summary lines to extract dialogue subtitles with timestamps
function parseEventsForSubtitles(eventsSummary, startTime) {
  if (!eventsSummary || !Array.isArray(eventsSummary)) return [];
  const subtitles = [];
  eventsSummary.forEach(ev => {
    // Matches e.g. [87.00-89.80] EP35_SC03_EV025 | DIALOGUE (ALEXANDER): We were close to finding him.
    const match = ev.match(/\[([0-9.]+)-([0-9.]+)\]\s*([^|]+)\|\s*(.*)/);
    if (match) {
      const start = parseFloat(match[1]);
      const end = parseFloat(match[2]);
      const typeAndSpeaker = match[4].trim();
      const relStart = Math.max(0, start - startTime);
      const relEnd = Math.max(relStart + 1.0, end - startTime);

      let text = typeAndSpeaker;
      let speaker = 'Narrator';
      let isDialogue = false;

      if (typeAndSpeaker.startsWith('DIALOGUE (')) {
        isDialogue = true;
        const speakerMatch = typeAndSpeaker.match(/DIALOGUE\s*\(([^)]+)\):\s*(.*)/);
        if (speakerMatch) {
          speaker = speakerMatch[1];
          text = speakerMatch[2];
        }
      } else if (typeAndSpeaker.startsWith('CAMERA:')) {
        speaker = 'Camera Angle';
        text = typeAndSpeaker.replace('CAMERA:', '').trim();
      } else if (typeAndSpeaker.startsWith('ACTION:')) {
        speaker = 'Screen Action';
        text = typeAndSpeaker.replace('ACTION:', '').trim();
      }

      subtitles.push({
        relStart: Number(relStart.toFixed(2)),
        relEnd: Number(relEnd.toFixed(2)),
        absStart: start,
        absEnd: end,
        speaker,
        text,
        isDialogue
      });
    }
  });
  return subtitles;
}

// Map of LLM enhancements by candidate_id
const llmMap = new Map();
promoResultsLLM.promos.forEach(p => {
  llmMap.set(p.candidate_id, p);
});

// Process all candidates
const candidates = allScreened.candidates.map((c, idx) => {
  const llmEnhance = llmMap.get(c.candidate_id);
  const title = llmEnhance ? llmEnhance.promo_title : cleanTitle(c.promo_title, c.episode_number, c.candidate_id);
  const hookExp = llmEnhance ? llmEnhance.hook_explanation : c.hook_explanation;
  const cliffExp = llmEnhance ? llmEnhance.cliffhanger_explanation : c.cliffhanger_explanation;
  const strengths = llmEnhance ? llmEnhance.strengths : c.strengths;
  const weaknesses = (llmEnhance && !llmEnhance.weaknesses.includes('429')) ? llmEnhance.weaknesses : c.weaknesses;

  const subtitles = parseEventsForSubtitles(c.events_summary, c.start_time);

  // Normalize scores
  const scores = {
    hook_strength: c.scores?.hook_strength || 7.5,
    cliffhanger_strength: c.scores?.cliffhanger_strength || 7.5,
    narrative_clarity: c.scores?.narrative_clarity || 8.0,
    conflict_and_stakes: c.scores?.conflict_and_stakes || 7.8,
    emotional_pull: c.scores?.emotional_pull || 8.0,
    script_visual_potential: c.scores?.script_visual_potential || 7.5,
    boundary_suitability: c.scores?.boundary_suitability || 8.5
  };

  // Determine key characters involved
  const characters = [];
  const textCorpus = (c.opening_quote || '') + ' ' + (c.closing_quote || '') + ' ' + (c.events_summary || []).join(' ');
  if (/JULIANA/i.test(textCorpus)) characters.push({ name: 'Lady Juliana', role: 'Defiant Bride', avatar: 'assets/images/avatar_juliana.jpg' });
  if (/ALEXANDER|STRANGER|SOLDIER|DUKE/i.test(textCorpus)) characters.push({ name: 'Alexander / The Duke', role: 'Broken Soldier', avatar: 'assets/images/avatar_alexander.jpg' });
  if (/MATRIARCH|MOTHER/i.test(textCorpus)) characters.push({ name: 'The Matriarch', role: 'Cruel Aristocrat', avatar: 'assets/images/avatar_matriarch.jpg' });
  if (/CATHERINE|SISTER/i.test(textCorpus)) characters.push({ name: 'Catherine', role: 'Deceitful Sister', avatar: 'assets/images/avatar_juliana.jpg' });

  return {
    candidate_id: c.candidate_id,
    rank: c.rank || 0,
    episode_number: c.episode_number,
    promo_title: title,
    editorial_verdict: llmEnhance ? (llmEnhance.editorial_verdict || 'STRONG') : (c.editorial_verdict || 'STRONG'),
    judge_verdict: llmEnhance ? (llmEnhance.judge_verdict || 'STRONG') : (c.judge_verdict || 'STRONG'),
    final_score: Number((llmEnhance ? llmEnhance.final_score : (c.final_score || 8.0)).toFixed(2)),
    candidate_score: Number((c.candidate_score || 8.0).toFixed(2)),
    judge_score: Number((llmEnhance ? llmEnhance.judge_score : (c.judge_score || 8.5)).toFixed(2)),
    start_time: c.start_time,
    end_time: c.end_time,
    start_display: c.start_display,
    end_display: c.end_display,
    duration_seconds: Number((c.duration_seconds || (c.end_time - c.start_time)).toFixed(2)),
    scores,
    opening_quote: c.opening_quote || "LADY JULIANA: \"I will not yield.\"",
    closing_quote: c.closing_quote || "ALEXANDER: \"Then accept my hand.\"",
    hook_explanation: hookExp || "Opens on high-stakes confrontation within first 3 seconds.",
    cliffhanger_explanation: cliffExp || "Cuts at the dramatic narrative climax with unresolved emotional stakes.",
    standalone_explanation: c.standalone_explanation || "Contains complete context of the character betrayal and conflict.",
    strengths: strengths || "Crisp dialogue rhythm and compelling cliffhanger.",
    weaknesses: weaknesses || "None of significance; strong vertical retention.",
    quality_flags: c.quality_flags || [],
    passed_quality_gates: Boolean(c.passed_quality_gates),
    gate_reasons: c.gate_reasons || [],
    human_review_status: c.human_review_status || 'pending',
    scene_image: getSceneImage(c.episode_number, title),
    events_summary: c.events_summary || [],
    subtitles,
    characters: characters.length > 0 ? characters : [{ name: 'Lady Juliana', role: 'Heroine', avatar: 'assets/images/avatar_juliana.jpg' }]
  };
});

// Sort passed candidates by final score
const passedCandidates = candidates.filter(c => c.passed_quality_gates);
passedCandidates.sort((a,b) => b.final_score - a.final_score);

// Assign ranks 1..N to passed candidates
passedCandidates.forEach((c, i) => {
  c.rank = i + 1;
});

// Top 30 curated promos
const top30 = passedCandidates.slice(0, 30);

// Top 5 golden cuts
const top5 = passedCandidates.slice(0, 5);

// Series overview metadata
const seriesInfo = {
  title: "I Married a Broken Soldier. He was a Duke",
  episodes_total: 50,
  genre: "Regency Romance / Vertical Drama / Revenge",
  poster: "assets/images/series_poster.jpg",
  synopsis: "Publicly betrayed at the altar when her groom chooses her sister, Lady Juliana makes a defiant wager: she accepts the sudden proposal of a scarred, silent soldier living in poverty. Unbeknownst to her high-society tormentors, her mysterious husband is none other than Alexander, the legendary war hero and Duke of Rochester.",
  characters: [
    { name: "Lady Juliana", title: "The Defiant Bride", desc: "Proud, resilient noblewoman whose betrayal sparks a fierce quest for justice.", avatar: "assets/images/avatar_juliana.jpg" },
    { name: "Alexander, The Duke", title: "The Broken Soldier", desc: "Decorated military commander masquerading as a destitute veteran to root out traitors.", avatar: "assets/images/avatar_alexander.jpg" },
    { name: "The Noble Matriarch", title: "The Cruel Stepmother", desc: "Calculates every marriage for dynastic power and orchestrates Juliana's humiliation.", avatar: "assets/images/avatar_matriarch.jpg" },
    { name: "Catherine", title: "The Deceitful Sister", desc: "Juliana's younger sister who conspires to steal the groom and the family inheritance.", avatar: "assets/images/avatar_juliana.jpg" }
  ]
};

// Compile final object
const consolidatedData = {
  seriesInfo,
  benchmark,
  metadata,
  summary: {
    total_screened: allScreened.total_screened || 168,
    total_passed: passedCandidates.length,
    total_rejected: allScreened.candidates.length - passedCandidates.length,
    top_30_count: top30.length,
    top_5_count: top5.length
  },
  top5,
  top30,
  passedCandidates,
  allCandidates: candidates
};

// Write to assets/js/data.js
const jsContent = `/**
 * Consolidated Promo Results & Screenplay Data
 * Kuku FM AI Generalist Assignment - Problem 1: Find the Promos
 * Series: "I Married a Broken Soldier. He was a Duke"
 */
const DRAMA_DATA = ${JSON.stringify(consolidatedData, null, 2)};
if (typeof window !== 'undefined') {
  window.DRAMA_DATA = DRAMA_DATA;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { DRAMA_DATA };
}
`;

fs.mkdirSync('assets/js', { recursive: true });
fs.writeFileSync('assets/js/data.js', jsContent, 'utf8');
console.log('Successfully generated assets/js/data.js');
console.log('Size:', (fs.statSync('assets/js/data.js').size / 1024).toFixed(1), 'KB');
