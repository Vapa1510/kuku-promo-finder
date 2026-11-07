# Offline-First Hybrid Promo Finder with Pluggable Gemini Evaluation Layer

A high-performance, explainable hybrid AI pipeline designed to parse full vertical drama screenplays (such as the 50-episode audio/video series *I Married a Broken Soldier. He was a Duke*), discover, evaluate, validate, and rank the highest-performing 20–60-second promotional clips for vertical video platforms.

The system is built as **Offline-First**: it executes with 100% deterministic reproducibility, zero score inflation, and strict evidence grounding in offline mode, while providing a pluggable **Gemini Evaluation Layer** (`--enable-llm`) when external Google GenAI credentials are configured.

---

## 🌐 Interactive Web Studio & Vercel Deployment

An end-to-end interactive UI studio is included in the workspace and ready for **instant Vercel deployment** with zero configuration:

- **Root `index.html`**: Bright, modern, high-end design palette with vibrant violet, rose, emerald, and royal blue accents.
- **Vercel Ready**: Preconfigured with `vercel.json` (zero build errors, sub-second deployment).
- **Interactive 9:16 Phone Simulator**: Dynamic Island notch, real-time timeline scrubber, synchronized subtitles, Web Audio procedural soundscape synthesizer, and live waveform visualizer canvas.
- **Zoom & Lightbox Modal**: High-res drama key art and scene stills with floating Zoom In (`+`), Zoom Out (`-`), and Reset (`100%`) controls.
- **7-Dimension Narrative Radar**: Interactive SVG radar chart comparing clips against dataset benchmark averages.
- **168 Candidate Audit Trail**: Full transparent filterable pipeline table across all 50 episodes.
- **Editorial Review Hub**: Approve / Request Recut / Reject workflow persisting to `localStorage` with **"Export Feedback CSV"** button.

### Quick Start:
```bash
# Preview locally (zero npm install required):
npm start

# Run automated 58-point test suite:
npm test
```
*See [DEPLOYMENT.md](DEPLOYMENT.md) for full 1-click Vercel deployment steps.*

---

## Architecture Overview

```
                                      ┌────────────────────────────────────────┐
                                      │   Raw Screenplay Files (50 Episodes)   │
                                      └───────────────────┬────────────────────┘
                                                          │
                                                          ▼
                                      ┌────────────────────────────────────────┐
                                      │   normalizer.py & parser.py            │
                                      │   (Normalized Timestamps & Event IDs)  │
                                      └───────────────────┬────────────────────┘
                                                          │
                                                          ▼
                                      ┌────────────────────────────────────────┐
                                      │   detector.py                          │
                                      │   (Non-Monotonic Endpoint Search,      │
                                      │    Scene-Scoped Continuous Candidates) │
                                      └─────────────┬──────────────────────────┘
                                                    │
                                                    ▼
                                      ┌────────────────────────────────────────┐
                                      │   heuristics.py                        │
                                      │   (Temporal [0, 3s] Hook &             │
                                      │    [T-3s, T] Cliffhanger Windowing)    │
                                      └───────┬──────────────────────┬─────────┘
                                              │                      │ (Optional)
                                              ▼                      ▼
                                      ┌─────────────────┐   ┌───────────────────────────┐
                                      │ evaluator.py    │   │ multi_segment_assembler.py│
                                      │ Deterministic   │   │ 2-3 Beat Cross-Scene Cut  │
                                      │ Offline / Gemini│   └─────────────┬─────────────┘
                                      │ Evaluation      │                 │
                                      └───────┬─────────┘                 │
                                              │ ◄─────────────────────────┘
                                              ▼
                                      ┌────────────────────────────────────────┐
                                      │ evidence_validator.py                  │
                                      │ (Strict [0, 3s] & [T-3s, T] Quotes,    │
                                      │  Verifiable Screenplay Event ID Proof) │
                                      └───────┬────────────────────────────────┘
                                              │
                                              ▼
                                      ┌────────────────────────────────────────┐
                                      │ judge.py                               │
                                      │ Pass/Fail Gate & Resolution Check      │
                                      │ (Pluggable LLM-as-a-Judge)             │
                                      └───────┬────────────────────────────────┘
                                              │
                                              ▼
                                      ┌────────────────────────────────────────┐
                                      │ ranker.py                              │
                                      │ Mandatory Evidence Gate & Quality Gates│
                                      │ (IoU <= 0.40, Max 2/ep Diversity Cap)  │
                                      └───────┬────────────────────────────────┘
                                              │
                         ┌────────────────────┼────────────────────┐
                         ▼                    ▼                    ▼
             outputs/promo_results.json  outputs/all_screened_  outputs/run_metadata.json
             outputs/promo_results.csv   candidates.json        outputs/human_feedback.csv
```

---

## Key Engineering Innovations

1. **Deterministic Python Core & Exact Boundary Snapping:**
   - Slices candidates strictly to atomic screenplay events (dialogue start to dialogue/action end).
   - Eliminates mid-sentence cuts, floating seconds, and timecode drift.
   - Non-monotonic endpoint search ensures overlapping events are not prematurely skipped.
   - Scopes continuous candidate generation strictly within the same scene.

2. **Temporal Windowing for Hooks and Cliffhangers:**
   - Evaluates opening hooks strictly within `[start_time, start_time + 3.0s]`.
   - Evaluates cliffhangers strictly within `[end_time - 3.0s, end_time]`.
   - Prevents whole-clip keywords from artificially inflating hook or cliffhanger metrics.

3. **Mandatory Evidence Quality Gate:**
   - Opening quotes are extracted strictly from dialogue/action in the first 3.0 seconds.
   - Closing quotes are extracted strictly from dialogue/action in the final 3.0 seconds.
   - If cited event IDs do not ground to genuine events or quotes are missing, `evidence_valid` is `False` and candidates are disqualified by quality gates.

4. **Calibrated Ranking & Dual-Pass Quality Gates:**
   - **Offline Mode (Default):** Final ranking score is driven 100% by the 7-dimension narrative score (`CandidateEvaluation.overall_score`), delivering a realistic, uninflated spread (e.g. 6.8–9.0). The `RuleBasedJudge` serves strictly as a deterministic pass/fail gatekeeper checking for premature resolution leaks and narrative coherence.
   - **LLM Mode (`--enable-llm`):** Pluggable Gemini 2.5 Flash evaluation with calibrated composite scoring `0.35 * candidate_score + 0.65 * judge_score`.

5. **Dramatic Marketing Titles:**
   - Replaces generic character strings with curated dramatic templates (`[Provisional Title] The Altar Betrayal`, `[Provisional Title] The Secret Proposal`, `[Provisional Title] The Cathedral Breach`, etc.).

6. **Input Fingerprinting & Checkpointing:**
   - Computes deterministic SHA256 input fingerprints across screenplay files and configuration settings.
   - Guarantees stale checkpoints are invalidated if screenplays or parameters change.
   - Saves progressive checkpoints every 10 candidates.

7. **Human Feedback Loop (`--import-feedback`):**
   - Direct CLI import for editorial review decisions (`APPROVED`, `REJECTED`, `NEEDS_RECUT`) with instant KPI metric calculation.

---

## Installation

Ensure Python 3.10+ is installed (or use `uv`):

```bash
uv pip install -r requirements.txt
```

---

## CLI Usage

### 1. Full 50-Episode Execution (Offline Mode)
Run the pipeline deterministically across all 50 episodes without external API dependencies:

```bash
python -m promo_finder.pipeline \
  --input "I Married a Broken Soldier. He was a Duke-scripts (2)/I Married a Broken Soldier. He was a Duke" \
  --output outputs \
  --top 30
```

### 2. Live Gemini LLM Execution
To use Gemini 2.5 Flash for primary evaluation and editorial judging:

```bash
# Set your Gemini API Key
export GEMINI_API_KEY="your-api-key"

python -m promo_finder.pipeline \
  --input "I Married a Broken Soldier. He was a Duke-scripts (2)/I Married a Broken Soldier. He was a Duke" \
  --output outputs \
  --top 30 \
  --enable-llm \
  --model "gemini-2.5-flash" \
  --judge-model "gemini-2.5-flash"
```

### 3. Multi-Segment Promo Assembly
To discover both continuous clips and stitched 2–3 beat cross-scene promotional sequences:

```bash
python -m promo_finder.pipeline \
  --input "I Married a Broken Soldier. He was a Duke-scripts (2)/I Married a Broken Soldier. He was a Duke" \
  --output outputs \
  --enable-multisegment
```

### 4. Custom Quality Gates and Thresholds
```bash
python -m promo_finder.pipeline \
  --input "I Married a Broken Soldier. He was a Duke-scripts (2)/I Married a Broken Soldier. He was a Duke" \
  --output outputs \
  --min-hook 7.0 \
  --min-cliff 7.0 \
  --min-clarity 6.0 \
  --iou-threshold 0.35 \
  --max-per-episode 1
### 5. Importing Human Editorial Feedback
To import reviewer decisions from an editorial spreadsheet and calculate team KPI acceptance rates:

```bash
python -m promo_finder.pipeline --import-feedback outputs/human_feedback.csv
```

---

## Generated Artifacts

| File | Purpose |
| :--- | :--- |
| `outputs/promo_results.json` | Top ranked, qualified promotional clips with detailed scores, timecodes, quotes, and explanations. |
| `outputs/promo_results.csv` | Flat spreadsheet summary for quick editorial scanning and video production workflow. |
| `outputs/all_screened_candidates.json` | 100% auditable record of all screened candidates, including gate failure reasons. |
| `outputs/model_responses.jsonl` | Complete prompt/response and decision trace logs. |
| `outputs/run_metadata.json` | Run provenance: configuration, episode counts, timings, and execution environment. |
| `outputs/human_feedback.csv` | Editorial sign-off template (`APPROVED`, `REJECTED`, `NEEDS_RECUT`). |

---

## Automated Testing

Run the full pytest suite (51 tests) covering all 11 modules:

```bash
pytest tests -v
```

Test coverage includes:
- Normalized timestamp conversions and label variations (e.g. Episode 6 uppercase headers).
- Boundary-snapped event alignments and non-monotonic endpoint windowing.
- Temporal windowing for hooks (`[0, 3s]`) and cliffhangers (`[T-3s, T]`).
- Context-bias-free regex signal detection.
- Primary narrative scoring and offline fallback.
- Calibrated offline score distribution and pass/fail judge gatekeeping.
- Mandatory evidence quality gate enforcement and verbatim quote verification.
- Temporal IoU deduplication and per-episode diversity caps.
- Multi-segment narrative assembly and duration validation.
- Input fingerprinting and checkpoint resumption.
- End-to-end pipeline integration and artifact validation.

---

## Benchmark Evaluation

Evaluate predicted promos against human-annotated ground truth (`evaluation/ground_truth.json`):

```bash
python -m evaluation.benchmark \
  --ground-truth evaluation/ground_truth.json \
  --predictions outputs/promo_results.json \
  --output evaluation/benchmark_report.json
```

Metrics reported:
- `Precision@K` ($K = 5, 10, 20, 30$)
- `Recall@K` ($K = 5, 10, 20, 30$)
- `NDCG@K` (Normalized Discounted Cumulative Gain)
- `Boundary MAE` (Start/End timestamp mean absolute error in seconds)
