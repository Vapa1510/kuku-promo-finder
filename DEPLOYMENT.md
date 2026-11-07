# DramaPulse Studio - Vercel Deployment & Local Preview Guide

This is the interactive web studio for **Kuku FM AI Generalist Assignment (Problem 1: Find the Promos)** evaluating the 50-episode vertical drama *"I Married a Broken Soldier. He was a Duke"*.

---

## 🚀 Live Vercel Deployment (Zero Configuration)

The project is structured as a high-performance, self-contained modern static web application with a root `vercel.json`. It deploys to **Vercel** with **zero build errors** and **zero npm dependencies required**.

### Method 1: Deploy via Vercel Dashboard (Recommended)
1. Push this repository to GitHub (or GitLab / Bitbucket).
2. Go to [https://vercel.com/new](https://vercel.com/new).
3. Import your repository.
4. Leave all settings at default:
   - **Framework Preset**: *Other*
   - **Root Directory**: `./`
   - **Build Command**: *(leave empty)*
   - **Output Directory**: `./`
5. Click **Deploy**. Your live site will be ready and globally available in ~10 seconds!

### Method 2: Deploy via Vercel CLI
```bash
# 1. Install Vercel CLI if you haven't already
npm install -g vercel

# 2. Login to your Vercel account
vercel login

# 3. Deploy to production
vercel --prod
```

---

## 💻 Local Preview Instructions

You can run and test the studio locally using any of the following lightweight methods:

### Method A: Built-in Node Server (Zero npm install)
```bash
npm start
```
*Starts a native Node.js HTTP server at `http://localhost:3000`.*

### Method B: Any Local Static Server
```bash
# Using npx serve:
npx serve .

# Using Python 3:
python -m http.server 3000
```
Open [http://localhost:3000](http://localhost:3000) in any modern web browser.

### Method C: Direct Browser Opening
Simply double-click or drag-and-drop `index.html` into Google Chrome, Microsoft Edge, Safari, or Firefox!

---

## 🧪 Automated Verification Test Suite

Run the built-in test suite to verify all 82 asset checks, universal CommonJS/browser data exports, Web Audio math safety, dual chart rendering, layout protections, and resolution endpoints:

```bash
npm test
# or
node test_ui.js
```

Expected output:
```
🎉 ALL 82 / 82 COMPREHENSIVE TESTS PASSED!
```

---

## 🎨 Interactive Features Showcase

1. **Bright & Professional Aesthetic**:
   - Modern glassmorphism palette with royal violet, rose crimson, emerald green, and crisp slate typography.
2. **Drama Visuals & High-Res Posters**:
   - High-definition series key art poster (`assets/images/series_poster.jpg`) with spotlight zoom inspection.
   - Character portrait avatars: *Lady Juliana*, *Duke Alexander*, *The Noble Matriarch*.
   - 9:16 vertical drama scene stills for altars, proposals, battles, and cathedral explosions.
3. **Interactive 9:16 Vertical Phone Simulator**:
   - Dynamic Island notch, status bar, and timecode ticker.
   - Interactive timeline scrubber with smooth mouse and touch drag scrubbing.
   - Real-time synchronized subtitle captions updating as the scrubber moves.
   - Procedural Web Audio engine synthesizing orchestral drones, heartbeat pulse, clock ticks, and cliffhanger risers with strict parameter scheduling safety.
   - Dynamic 24-bar audio waveform visualizer canvas connected directly to Web Audio analyzer node with smooth idle sine animation.
4. **Interactive Lightbox Modal with Zoom-In / Zoom-Out & Pan**:
   - Click any promo thumbnail or series key art poster to open high-res modal.
   - Floating zoom controls: Zoom In (`+`), Zoom Out (`-`), and Reset (`100%`).
   - Interactive mouse wheel zoom and click-and-drag pan when zoomed in.
   - Complete event-by-event transcript list with color-coded speaker and camera badges.
5. **Dual Narrative Analytics Chart Engine (Radar Web & Bar Comparison)**:
   - Interactive SVG radar chart covering all 7 narrative dimensions.
   - Interactive comparative bar chart mode with side-by-side benchmark deltas.
   - Candidate picker dropdown in Tab 2 to analyze any candidate.
6. **Full Candidate Audit Trail (168 Candidates)**:
   - Searchable, filterable table of all 168 screened segments across all 50 episodes.
   - Quality gate filter (Passed: 89, Rejected: 79) with explicit diagnostic reasons, episode filter, and keyword search.
7. **Editorial Review Workflow & CSV Export**:
   - One-click "Approve" (✓), "Request Recut" (✎), and "Reject" (✕) buttons with toggle support.
   - Status filters (All, Pending, Approved, Recut, Rejected) with dynamic counts.
   - Inline editable editorial review notes per candidate.
   - Micro-animated KPI badge updates with scale-and-glow effect.
   - **"Export Feedback CSV"** button downloads a production-ready CSV with UTF-8 BOM formatted to `outputs/human_feedback.csv`.
