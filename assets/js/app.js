/**
 * DramaPulse Studio - Main Application Controller
 * High-end vertical drama promo selection and interactive preview platform.
 * Features:
 * - Dynamic view mode switching (Top 30, Top 5, Passed 89, All 168)
 * - Multi-criteria search and filter engine (episode, duration, score slider, verdict)
 * - Interactive 9:16 vertical smartphone player with synchronized dialogue subtitles
 * - Procedural Web Audio API soundscape with dynamic 24-bar visualizer
 * - Interactive scrubber with mouse/touch drag scrubbing and seamless audio resync
 * - 7-dimension narrative scoring with dual Radar Web and Bar Comparison chart modes
 * - Candidate selector in diagnostics tab
 * - Full 168-candidate audit trail with gate diagnostic logs and episode/keyword search
 * - Comprehensive benchmark evaluation report with K=5..30 matrix & pipeline provenance
 * - Editorial review workflow with inline notes, status filtering, and CSV export (UTF-8 BOM)
 * - Fullscreen lightbox with zoom-in/out, mouse wheel zoom, pan/drag, and series key art mode
 * - Micro-animated KPI badge updates
 */

(function () {
  'use strict';

  // 1. Application State
  const state = {
    data: (typeof window !== 'undefined' && window.DRAMA_DATA) ? window.DRAMA_DATA : null,
    activeTab: 'showcase',
    viewMode: 'top30', // 'top30' | 'top5' | 'passed' | 'all'
    searchQuery: '',
    selectedEpisode: 'all',
    minScore: 5.0,
    durationFilter: 'all',
    verdictFilter: 'all',
    sortBy: 'rank',

    // Active promo loaded in the 9:16 phone simulator
    activePromo: null,

    // Editorial decisions stored locally
    editorialDecisions: {},
    editorialStatusFilter: 'all', // 'all' | 'PENDING' | 'APPROVED' | 'RECUT' | 'REJECTED'

    // Candidate Audit trail filters
    auditSearchQuery: '',
    auditEpisodeFilter: 'all',
    auditGateFilter: 'all',

    // Playback state
    playback: {
      isPlaying: false,
      currentTime: 0,
      duration: 38.5,
      intervalId: null,
      isDraggingScrubber: false
    },

    // Lightbox Zoom & Pan state
    zoom: {
      level: 1.0,
      min: 0.6,
      max: 3.0,
      step: 0.25,
      panX: 0,
      panY: 0,
      isPanning: false,
      startX: 0,
      startY: 0
    },

    // Diagnostics chart
    chartMode: 'radar', // 'radar' | 'bars'
    radarPromoId: null,

    // Engines
    audioEngine: null,
    radarEngine: null,
    socialLikes: {}
  };

  // 2. Initialization
  function init() {
    if (!state.data) {
      console.error('Drama data not loaded.');
      return;
    }

    // Load stored editorial decisions from localStorage
    loadEditorialStorage();

    // Default active promo is rank 1
    state.activePromo = (state.data.top5 && state.data.top5[0]) || (state.data.top30 && state.data.top30[0]) || state.data.allCandidates[0];
    state.playback.duration = state.activePromo ? state.activePromo.duration_seconds : 38.5;
    state.radarPromoId = state.activePromo ? state.activePromo.candidate_id : null;

    // Initialize Audio & Radar engines
    if (window.DramaAudioEngine) {
      state.audioEngine = new window.DramaAudioEngine();
    }
    if (window.RadarChartEngine) {
      state.radarEngine = new window.RadarChartEngine('radarChartContainer');
    }

    // Setup visualizer callback to draw waveform on canvas
    const canvas = document.getElementById('phoneWaveformCanvas');
    if (canvas) {
      const ctx = canvas.getContext('2d');
      if (state.audioEngine) {
        state.audioEngine.onVisualizerUpdate = (freqData) => {
          drawWaveform(ctx, canvas.width, canvas.height, freqData);
        };
        state.audioEngine.onStop = () => {
          drawIdleWaveform(ctx, canvas.width, canvas.height);
        };
      }
      // Draw initial idle wave immediately so canvas is never blank
      drawIdleWaveform(ctx, canvas.width, canvas.height);
    }

    // Render Initial UI Elements
    populateEpisodeDropdowns();
    populateRadarPromoDropdown();
    updateKpiCounters();
    bindEvents();
    renderActiveTab();
    updatePhonePreview();
  }

  // 3. LocalStorage Editorial Reviews
  function loadEditorialStorage() {
    try {
      const saved = localStorage.getItem('kuku_editorial_feedback');
      if (saved) {
        state.editorialDecisions = JSON.parse(saved);
      }
    } catch (e) {
      console.warn('Could not read localStorage', e);
    }
  }

  function saveEditorialDecision(candidateId, decision, notes = null) {
    const existing = state.editorialDecisions[candidateId] || {};
    const currentDecision = existing.decision;

    // If clicking an already active decision, toggle it back to PENDING
    const newDecision = (currentDecision === decision && notes === null) ? 'PENDING' : decision;

    state.editorialDecisions[candidateId] = {
      candidate_id: candidateId,
      decision: newDecision,
      notes: notes !== null ? notes : (existing.notes || ''),
      timestamp: new Date().toISOString()
    };

    try {
      localStorage.setItem('kuku_editorial_feedback', JSON.stringify(state.editorialDecisions));
    } catch (e) {}

    updateKpiCounters(true);
    showToast(`Decision "${newDecision}" recorded for ${candidateId}`);
    renderActiveTab();
  }

  function saveEditorialNote(candidateId, noteText) {
    const existing = state.editorialDecisions[candidateId] || {};
    state.editorialDecisions[candidateId] = {
      candidate_id: candidateId,
      decision: existing.decision || 'PENDING',
      notes: noteText.trim(),
      timestamp: new Date().toISOString()
    };
    try {
      localStorage.setItem('kuku_editorial_feedback', JSON.stringify(state.editorialDecisions));
    } catch (e) {}
    showToast(`Editorial note saved for ${candidateId}`);
  }

  // 4. Filter and Search Logic for Showcase View
  function getFilteredPromos() {
    let pool = [];
    if (state.viewMode === 'top5') {
      pool = [...state.data.top5];
    } else if (state.viewMode === 'top30') {
      pool = [...state.data.top30];
    } else if (state.viewMode === 'passed') {
      pool = [...state.data.passedCandidates];
    } else {
      pool = [...state.data.allCandidates];
    }

    return pool.filter(item => {
      // Search query
      if (state.searchQuery) {
        const q = state.searchQuery.toLowerCase();
        const text = `${item.promo_title} ${item.candidate_id} ${item.opening_quote} ${item.closing_quote} ${item.strengths} ${item.weaknesses}`.toLowerCase();
        if (!text.includes(q)) return false;
      }

      // Episode filter
      if (state.selectedEpisode !== 'all') {
        if (item.episode_number !== parseInt(state.selectedEpisode, 10)) return false;
      }

      // Min score filter
      if (item.final_score < state.minScore) return false;

      // Duration filter
      if (state.durationFilter === 'short' && item.duration_seconds >= 35) return false;
      if (state.durationFilter === 'medium' && (item.duration_seconds < 35 || item.duration_seconds > 45)) return false;
      if (state.durationFilter === 'long' && item.duration_seconds <= 45) return false;

      // Editorial Verdict filter
      if (state.verdictFilter !== 'all') {
        const review = state.editorialDecisions[item.candidate_id]?.decision;
        if (state.verdictFilter === 'APPROVED' && review !== 'APPROVED') return false;
        if (state.verdictFilter === 'RECUT' && review !== 'RECUT') return false;
        if (state.verdictFilter === 'REJECTED' && review !== 'REJECTED') return false;
        if (state.verdictFilter === 'STRONG' && item.editorial_verdict !== 'STRONG') return false;
        if (state.verdictFilter === 'MUST INCLUDE' && item.editorial_verdict !== 'MUST INCLUDE') return false;
      }

      return true;
    }).sort((a, b) => {
      if (state.sortBy === 'rank') return (a.rank || 999) - (b.rank || 999);
      if (state.sortBy === 'score_desc') return b.final_score - a.final_score;
      if (state.sortBy === 'score_asc') return a.final_score - b.final_score;
      if (state.sortBy === 'duration_desc') return b.duration_seconds - a.duration_seconds;
      if (state.sortBy === 'duration_asc') return a.duration_seconds - b.duration_seconds;
      if (state.sortBy === 'episode') return a.episode_number - b.episode_number;
      if (state.sortBy === 'hook') return (b.scores?.hook_strength || 0) - (a.scores?.hook_strength || 0);
      if (state.sortBy === 'cliffhanger') return (b.scores?.cliffhanger_strength || 0) - (a.scores?.cliffhanger_strength || 0);
      return 0;
    });
  }

  // 5. Dropdown Populators
  function populateEpisodeDropdowns() {
    const epSelect = document.getElementById('episodeSelect');
    const auditEpSelect = document.getElementById('auditEpisodeSelect');
    const episodes = new Set(state.data.allCandidates.map(c => c.episode_number));
    const sorted = Array.from(episodes).sort((a, b) => a - b);

    let html = '<option value="all">All Episodes (1 - 50)</option>';
    sorted.forEach(ep => {
      html += `<option value="${ep}">Episode ${ep}</option>`;
    });

    if (epSelect) epSelect.innerHTML = html;
    if (auditEpSelect) auditEpSelect.innerHTML = html;
  }

  function populateRadarPromoDropdown() {
    const select = document.getElementById('radarPromoSelect');
    if (!select) return;

    const list = state.data.top30 || state.data.passedCandidates || [];
    let html = '';
    list.forEach(p => {
      const isSelected = p.candidate_id === state.radarPromoId ? 'selected' : '';
      html += `<option value="${p.candidate_id}" ${isSelected}>Rank #${p.rank || '-'} • Ep ${p.episode_number} • ${escapeHtml(p.promo_title)} (Score: ${p.final_score})</option>`;
    });
    select.innerHTML = html;
  }

  // 6. Update KPI Counters with Micro-Animations
  function updateKpiCounters(animate = false) {
    const approvedCount = Object.values(state.editorialDecisions).filter(d => d.decision === 'APPROVED').length;
    const reviewedCount = Object.values(state.editorialDecisions).filter(d => d.decision && d.decision !== 'PENDING').length;
    const totalDecisions = Object.keys(state.editorialDecisions).length;

    const kpiApproved = document.getElementById('kpiApprovedCount');
    if (kpiApproved) {
      kpiApproved.innerText = reviewedCount;
      if (animate) triggerMicroAnimation(kpiApproved);
    }

    const kpiPassRate = document.getElementById('kpiPassRate');
    if (kpiPassRate) {
      const rate = reviewedCount > 0 ? Math.round((approvedCount / reviewedCount) * 100) : 0;
      kpiPassRate.innerHTML = `${rate}<span>%</span>`;
      if (animate) triggerMicroAnimation(kpiPassRate);
    }

    // Update Editorial Hub count pills
    const allPassedCount = (state.data.passedCandidates || []).length;
    const edApproved = Object.values(state.editorialDecisions).filter(d => d.decision === 'APPROVED').length;
    const edRecut = Object.values(state.editorialDecisions).filter(d => d.decision === 'RECUT').length;
    const edRejected = Object.values(state.editorialDecisions).filter(d => d.decision === 'REJECTED').length;
    const edPending = allPassedCount - (edApproved + edRecut + edRejected);

    const cAll = document.getElementById('edFilterAllCount');
    const cPen = document.getElementById('edFilterPendingCount');
    const cApp = document.getElementById('edFilterApprovedCount');
    const cRec = document.getElementById('edFilterRecutCount');
    const cRej = document.getElementById('edFilterRejectedCount');

    if (cAll) cAll.innerText = allPassedCount;
    if (cPen) cPen.innerText = Math.max(0, edPending);
    if (cApp) cApp.innerText = edApproved;
    if (cRec) cRec.innerText = edRecut;
    if (cRej) cRej.innerText = edRejected;
  }

  function triggerMicroAnimation(el) {
    el.classList.remove('kpi-animating');
    void el.offsetWidth; // trigger reflow
    el.classList.add('kpi-animating');
    setTimeout(() => el.classList.remove('kpi-animating'), 500);
  }

  // 7. Render Active Tab
  function renderActiveTab() {
    const tabShowcase = document.getElementById('tabContentShowcase');
    const tabRadar = document.getElementById('tabContentRadar');
    const tabAudit = document.getElementById('tabContentAudit');
    const tabBenchmark = document.getElementById('tabContentBenchmark');
    const tabEditorial = document.getElementById('tabContentEditorial');

    if (tabShowcase) tabShowcase.style.display = state.activeTab === 'showcase' ? 'block' : 'none';
    if (tabRadar) tabRadar.style.display = state.activeTab === 'radar' ? 'block' : 'none';
    if (tabAudit) tabAudit.style.display = state.activeTab === 'audit' ? 'block' : 'none';
    if (tabBenchmark) tabBenchmark.style.display = state.activeTab === 'benchmark' ? 'block' : 'none';
    if (tabEditorial) tabEditorial.style.display = state.activeTab === 'editorial' ? 'block' : 'none';

    // Highlight active nav tab button
    document.querySelectorAll('.tab-btn').forEach(btn => {
      const target = btn.getAttribute('data-tab');
      if (target === state.activeTab) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    if (state.activeTab === 'showcase') {
      renderPromoGrid();
    } else if (state.activeTab === 'radar') {
      renderRadarView();
    } else if (state.activeTab === 'audit') {
      renderAuditView();
    } else if (state.activeTab === 'benchmark') {
      renderBenchmarkView();
    } else if (state.activeTab === 'editorial') {
      renderEditorialHubView();
    }
  }

  // 8. Render Promo Grid (Showcase View)
  function renderPromoGrid() {
    const container = document.getElementById('promoCardsGrid');
    if (!container) return;

    const items = getFilteredPromos();

    // Update counts badge
    const countBadge = document.getElementById('resultsCountBadge');
    if (countBadge) {
      countBadge.innerText = `${items.length} clips found`;
    }

    // Update tab showcase count
    const tabCount = document.getElementById('tabShowcaseCount');
    if (tabCount) {
      let poolSize = 30;
      if (state.viewMode === 'top5') poolSize = 5;
      else if (state.viewMode === 'top30') poolSize = 30;
      else if (state.viewMode === 'passed') poolSize = 89;
      else if (state.viewMode === 'all') poolSize = 168;
      tabCount.innerText = poolSize;
    }

    if (items.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 60px 20px; text-align: center; background: white; border-radius: 16px; border: 1px dashed #CBD5E1;">
          <div style="font-size: 36px; margin-bottom: 12px;">🔍</div>
          <h3 style="font-size: 18px; font-weight: 700; color: #1E293B;">No matching promo clips found</h3>
          <p style="color: #64748B; font-size: 14px; margin-top: 6px;">Try adjusting your score filter, duration, or search keyword.</p>
          <button id="resetFiltersBtn" class="btn-primary" style="margin-top: 16px;">Reset All Filters</button>
        </div>
      `;
      const rBtn = document.getElementById('resetFiltersBtn');
      if (rBtn) rBtn.addEventListener('click', resetFilters);
      return;
    }

    let html = '';
    items.forEach(p => {
      const decision = state.editorialDecisions[p.candidate_id]?.decision;
      let rankClass = '';
      if (p.rank === 1) rankClass = 'rank-gold';
      else if (p.rank === 2) rankClass = 'rank-silver';
      else if (p.rank === 3) rankClass = 'rank-bronze';

      const isCurrentActive = state.activePromo?.candidate_id === p.candidate_id;

      html += `
        <div class="promo-card ${isCurrentActive ? 'active' : ''}" data-id="${p.candidate_id}" onclick="window.DramaApp.onCardClick(event, '${p.candidate_id}')">
          <div class="card-thumbnail-box" onclick="event.stopPropagation(); window.DramaApp.openLightbox('${p.candidate_id}')" title="Click to Zoom Still">
            <img src="${p.scene_image}" alt="${escapeHtml(p.promo_title)}" loading="lazy">
            <div class="card-rank-badge ${rankClass}">
              <span>#${p.rank || '-'}</span>
            </div>
            <div class="card-duration-badge">⏱ ${p.duration_seconds}s</div>
            <div class="card-zoom-overlay" title="Zoom & Full Screen">🔍</div>
          </div>

          <div class="card-body">
            <div class="card-meta-row">
              <span class="ep-tag">EP ${p.episode_number}</span>
              <span class="score-badge ${p.final_score >= 8.5 ? 'score-high' : 'score-med'}">
                ⭐ ${p.final_score.toFixed(1)} / 10
              </span>
            </div>

            <h3 class="card-title" title="${escapeHtml(p.promo_title)}">${escapeHtml(p.promo_title)}</h3>

            <div class="card-quotes">
              <div><strong>Open:</strong> ${escapeHtml(p.opening_quote)}</div>
              <div><strong>Climax:</strong> ${escapeHtml(p.closing_quote)}</div>
            </div>

            <div class="mini-dimensions">
              <div class="dim-bar-row">
                <span class="dim-bar-label">Hook Strength</span>
                <span class="dim-bar-val">${p.scores?.hook_strength || 8}/10</span>
              </div>
              <div class="dim-bar-track">
                <div class="dim-bar-fill" style="width: ${(p.scores?.hook_strength || 8) * 10}%"></div>
              </div>

              <div class="dim-bar-row" style="margin-top: 4px;">
                <span class="dim-bar-label">Cliffhanger Climax</span>
                <span class="dim-bar-val">${p.scores?.cliffhanger_strength || 8}/10</span>
              </div>
              <div class="dim-bar-track">
                <div class="dim-bar-fill" style="width: ${(p.scores?.cliffhanger_strength || 8) * 10}%"></div>
              </div>
            </div>
          </div>

          <div class="card-footer" onclick="event.stopPropagation()">
            <button class="preview-btn" onclick="window.DramaApp.selectAndPlay('${p.candidate_id}')">
              <span>▶ Play Preview</span>
            </button>

            <div class="editorial-btn-group">
              <button class="editorial-btn approve ${decision === 'APPROVED' ? 'active' : ''}" title="Approve Promo" onclick="window.DramaApp.markEditorial('${p.candidate_id}', 'APPROVED')">✓</button>
              <button class="editorial-btn recut ${decision === 'RECUT' ? 'active' : ''}" title="Request Recut" onclick="window.DramaApp.markEditorial('${p.candidate_id}', 'RECUT')">✎</button>
              <button class="editorial-btn reject ${decision === 'REJECTED' ? 'active' : ''}" title="Reject Promo" onclick="window.DramaApp.markEditorial('${p.candidate_id}', 'REJECTED')">✕</button>
            </div>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  }

  // 9. Phone Preview Controller & Simulator
  function updatePhonePreview() {
    const promo = state.activePromo;
    if (!promo) return;

    const phoneImg = document.getElementById('phoneBgImage');
    if (phoneImg) phoneImg.src = promo.scene_image;

    const phoneEpBadge = document.getElementById('phoneEpBadge');
    if (phoneEpBadge) phoneEpBadge.innerText = `EPISODE ${promo.episode_number}`;

    const phoneTitle = document.getElementById('phoneTitle');
    if (phoneTitle) phoneTitle.innerText = promo.promo_title;

    const phoneDuration = document.getElementById('phoneTotalTime');
    if (phoneDuration) phoneDuration.innerText = formatTime(promo.duration_seconds);

    state.playback.duration = promo.duration_seconds;
    seekPlayback(0);

    // Update Likes counter
    const likeBtn = document.getElementById('phoneLikeBtn');
    const likeCount = document.getElementById('phoneLikeCount');
    const likes = state.socialLikes[promo.candidate_id] || (12400 + (promo.rank || 5) * 180);
    if (likeCount) likeCount.innerText = formatK(likes);
    if (likeBtn) {
      if (state.socialLikes[promo.candidate_id]) likeBtn.classList.add('liked');
      else likeBtn.classList.remove('liked');
    }
  }

  function togglePlayback() {
    if (state.playback.isPlaying) {
      pausePlayback();
    } else {
      startPlayback();
    }
  }

  function startPlayback() {
    state.playback.isPlaying = true;
    const playBtn = document.getElementById('phonePlayBtn');
    if (playBtn) playBtn.innerHTML = '❚❚';

    // Start procedural sound engine with remaining time
    const remainingTime = Math.max(0.6, state.playback.duration - state.playback.currentTime);
    if (state.audioEngine) {
      state.audioEngine.start(remainingTime);
    }

    // Playback loop
    const stepMs = 50;
    if (state.playback.intervalId) clearInterval(state.playback.intervalId);

    state.playback.intervalId = setInterval(() => {
      if (state.playback.isDraggingScrubber) return;

      state.playback.currentTime += stepMs / 1000;
      if (state.playback.currentTime >= state.playback.duration) {
        seekPlayback(0);
        pausePlayback();
        return;
      }
      updatePlaybackUI();
    }, stepMs);
  }

  function pausePlayback() {
    state.playback.isPlaying = false;
    const playBtn = document.getElementById('phonePlayBtn');
    if (playBtn) playBtn.innerHTML = '▶';

    if (state.playback.intervalId) {
      clearInterval(state.playback.intervalId);
      state.playback.intervalId = null;
    }
    if (state.audioEngine) {
      state.audioEngine.stop();
    }

    // Reset visualizer waveform back to idle
    const canvas = document.getElementById('phoneWaveformCanvas');
    if (canvas) {
      drawIdleWaveform(canvas.getContext('2d'), canvas.width, canvas.height);
    }
  }

  function seekPlayback(targetSeconds) {
    state.playback.currentTime = Math.max(0, Math.min(state.playback.duration, targetSeconds));
    updatePlaybackUI();

    // If currently playing, resynchronize procedural audio with the new remaining duration
    if (state.playback.isPlaying && state.audioEngine) {
      const remainingTime = Math.max(0.6, state.playback.duration - state.playback.currentTime);
      state.audioEngine.start(remainingTime);
    }
  }

  function updatePlaybackUI() {
    const curTime = state.playback.currentTime;
    const totalTime = state.playback.duration;

    // Time text
    const curTimeEl = document.getElementById('phoneCurrentTime');
    if (curTimeEl) curTimeEl.innerText = formatTime(curTime);

    // Scrubber fill & handle
    const fillEl = document.getElementById('timelineFill');
    const handleEl = document.getElementById('timelineHandle');
    const percent = Math.min(100, (curTime / totalTime) * 100);
    if (fillEl) fillEl.style.width = `${percent}%`;
    if (handleEl) handleEl.style.left = `${percent}%`;

    // Hook vs Cliffhanger indicator
    const hookLivePill = document.getElementById('hookLivePill');
    if (hookLivePill) {
      if (curTime <= 3.5) {
        hookLivePill.innerText = '⚡ LIVE HOOK (0-3s)';
        hookLivePill.style.background = 'rgba(16, 185, 129, 0.95)';
      } else if (curTime >= totalTime - 3.5) {
        hookLivePill.innerText = '🔥 CLIFFHANGER CUT';
        hookLivePill.style.background = 'rgba(244, 63, 94, 0.95)';
      } else {
        hookLivePill.innerText = '▶ NARRATIVE CORE';
        hookLivePill.style.background = 'rgba(37, 99, 235, 0.9)';
      }
    }

    // Dynamic Subtitle update
    updateActiveSubtitle(curTime);
  }

  function updateActiveSubtitle(curTime) {
    const captionBox = document.getElementById('phoneCaptionBox');
    const speakerEl = document.getElementById('captionSpeaker');
    const textEl = document.getElementById('captionText');
    if (!captionBox || !speakerEl || !textEl || !state.activePromo) return;

    const subs = state.activePromo.subtitles || [];
    let activeSub = null;

    for (let s of subs) {
      if (curTime >= s.relStart && curTime <= s.relEnd) {
        activeSub = s;
        break;
      }
    }

    if (!activeSub) {
      if (curTime < 5) {
        speakerEl.innerText = 'Opening Beat';
        textEl.innerText = state.activePromo.opening_quote;
      } else if (curTime > state.playback.duration - 5) {
        speakerEl.innerText = 'Cliffhanger Climax';
        textEl.innerText = state.activePromo.closing_quote;
      } else {
        speakerEl.innerText = 'Dramatic Escalation';
        textEl.innerText = (state.activePromo.strengths || '').slice(0, 75) + '...';
      }
    } else {
      speakerEl.innerText = activeSub.speaker;
      textEl.innerText = activeSub.text;
    }
  }

  // Draw Dynamic Audio Waveform on Canvas
  function drawWaveform(ctx, width, height, freqData) {
    ctx.clearRect(0, 0, width, height);
    if (!state.playback.isPlaying || !freqData) {
      drawIdleWaveform(ctx, width, height);
      return;
    }

    const bars = 24;
    const barWidth = width / bars;
    const gradient = ctx.createLinearGradient(0, height, 0, 0);
    gradient.addColorStop(0, '#7C3AED');
    gradient.addColorStop(0.5, '#EC4899');
    gradient.addColorStop(1, '#F43F5E');
    ctx.fillStyle = gradient;

    for (let i = 0; i < bars; i++) {
      // Sample and interpolate across available frequency bins with gaussian envelope
      const binIdx = Math.floor((i / bars) * (freqData.length * 0.7));
      const rawVal = freqData[binIdx] || 0;
      const energyFactor = 0.5 + 0.5 * Math.sin((i / bars) * Math.PI);
      const scaledVal = Math.max(rawVal * energyFactor, (rawVal * 0.4) + Math.sin(Date.now() * 0.01 + i) * 15);
      const barHeight = Math.max(3, Math.min(height, (scaledVal / 255) * height * 1.2));
      ctx.fillRect(i * barWidth + 1, height - barHeight, barWidth - 2, barHeight);
    }
  }

  function drawIdleWaveform(ctx, width, height) {
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = '#64748B';
    const bars = 24;
    const barWidth = width / bars;
    for (let i = 0; i < bars; i++) {
      const h = 3 + Math.sin(i * 0.5 + Date.now() * 0.002) * 2;
      ctx.fillRect(i * barWidth + 1, height - h, barWidth - 2, h);
    }
  }

  // 10. Radar Chart Tab Controller
  function renderRadarView() {
    const promo = state.data.allCandidates.find(c => c.candidate_id === state.radarPromoId) || state.activePromo;
    if (!promo || !state.radarEngine) return;

    // Benchmark average baseline for comparison
    const benchmarkScores = {
      hook_strength: 8.2,
      cliffhanger_strength: 8.4,
      narrative_clarity: 8.0,
      conflict_and_stakes: 8.5,
      emotional_pull: 8.1,
      script_visual_potential: 7.9,
      boundary_suitability: 8.8
    };

    state.radarEngine.render(promo.scores, benchmarkScores, promo.promo_title, 'Benchmark Average');

    // Update diagnostic breakdown list
    const breakdownList = document.getElementById('radarBreakdownList');
    if (breakdownList) {
      let html = '';
      const dims = [
        { key: 'hook_strength', name: '1. Hook Strength', weight: '20%', desc: 'Opening 0-3s retention trigger and narrative question' },
        { key: 'cliffhanger_strength', name: '2. Cliffhanger Climax', weight: '20%', desc: 'Final 3s unresolved emotional or physical crisis' },
        { key: 'narrative_clarity', name: '3. Narrative Clarity', weight: '15%', desc: 'Standalone comprehensibility without episode context' },
        { key: 'conflict_and_stakes', name: '4. Conflict & Stakes', weight: '15%', desc: 'Interpersonal betrayal, danger, or dynastic feud' },
        { key: 'emotional_pull', name: '5. Emotional Pull', weight: '10%', desc: 'Audience empathy with Lady Juliana and Duke Alexander' },
        { key: 'script_visual_potential', name: '6. Script Visual Potential', weight: '10%', desc: 'Cinematic camera cues, explosions, swordplay, candles' },
        { key: 'boundary_suitability', name: '7. Boundary Suitability', weight: '10%', desc: 'Sub-2s dialogue frame cut precision without clipping' }
      ];

      dims.forEach(d => {
        const val = promo.scores[d.key] !== undefined ? promo.scores[d.key] : 8.0;
        const bVal = benchmarkScores[d.key];
        const delta = (val - bVal).toFixed(1);
        const deltaSign = val >= bVal ? `+${delta}` : delta;
        const deltaColor = val >= bVal ? 'color: #059669;' : 'color: #D97706;';

        html += `
          <div style="background: white; border-radius: 12px; padding: 14px 18px; border: 1px solid #E2E8F0; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
            <div>
              <div style="font-weight: 700; font-size: 14px; color: #1E293B;">${d.name} <span style="font-size: 11px; font-weight: 600; color: #7C3AED; background: #EDE9FE; padding: 2px 6px; border-radius: 99px;">Weight: ${d.weight}</span></div>
              <div style="font-size: 12px; color: #64748B; margin-top: 2px;">${d.desc}</div>
            </div>
            <div style="text-align: right;">
              <div style="font-size: 18px; font-weight: 800; color: #1E293B;">${val} <span style="font-size: 12px; font-weight: 600; color: #94A3B8;">/10</span></div>
              <div style="font-size: 11px; font-weight: 700; ${deltaColor}">vs Bench: ${deltaSign}</div>
            </div>
          </div>
        `;
      });
      breakdownList.innerHTML = html;
    }
  }

  // 11. Full Candidate Audit Trail Tab (168 Candidates)
  function renderAuditView() {
    const tableBody = document.getElementById('auditTableBody');
    if (!tableBody) return;

    const candidates = state.data.allCandidates || [];

    const filtered = candidates.filter(c => {
      // Gate filter
      if (state.auditGateFilter === 'passed' && !c.passed_quality_gates) return false;
      if (state.auditGateFilter === 'rejected' && c.passed_quality_gates) return false;

      // Episode filter
      if (state.auditEpisodeFilter !== 'all') {
        if (c.episode_number !== parseInt(state.auditEpisodeFilter, 10)) return false;
      }

      // Search query
      if (state.auditSearchQuery) {
        const q = state.auditSearchQuery.toLowerCase();
        const text = `${c.candidate_id} ${c.promo_title} ${c.opening_quote} ${c.closing_quote}`.toLowerCase();
        if (!text.includes(q)) return false;
      }

      return true;
    });

    let html = '';
    filtered.forEach((c, i) => {
      const gateStatus = c.passed_quality_gates
        ? `<span style="background: #D1FAE5; color: #065F46; padding: 3px 8px; border-radius: 99px; font-size: 11px; font-weight: 700;">✓ PASSED</span>`
        : `<span style="background: #FFE4E6; color: #9F1239; padding: 3px 8px; border-radius: 99px; font-size: 11px; font-weight: 700;">✕ GATED</span>`;

      const reasons = c.gate_reasons && c.gate_reasons.length > 0
        ? `<span style="font-size: 11px; color: #DC2626;">${escapeHtml(c.gate_reasons.join(', '))}</span>`
        : `<span style="font-size: 11px; color: #059669;">All quality criteria satisfied</span>`;

      html += `
        <tr>
          <td style="font-weight: 700;">#${i + 1}</td>
          <td><code style="background: #F1F5F9; padding: 2px 6px; border-radius: 4px; font-size: 11px;">${c.candidate_id}</code></td>
          <td><span class="ep-tag">EP ${c.episode_number}</span></td>
          <td style="font-weight: 600;">${escapeHtml(c.promo_title)}</td>
          <td>${c.start_display} - ${c.end_display}</td>
          <td style="font-weight: 700;">${c.duration_seconds}s</td>
          <td style="font-weight: 800; color: #7C3AED;">${c.final_score.toFixed(1)}</td>
          <td>${gateStatus}</td>
          <td>${reasons}</td>
          <td>
            <div style="display: flex; gap: 6px;">
              <button class="preview-btn" style="padding: 4px 10px; font-size: 11px;" onclick="window.DramaApp.openLightbox('${c.candidate_id}')">Inspect</button>
              <button class="preview-btn" style="padding: 4px 10px; font-size: 11px; background: #0F172A;" onclick="window.DramaApp.selectAndPlay('${c.candidate_id}')">▶</button>
            </div>
          </td>
        </tr>
      `;
    });

    tableBody.innerHTML = html || `<tr><td colspan="10" style="text-align: center; padding: 32px; color: #64748B;">No candidates match your filters.</td></tr>`;
  }

  // 12. Benchmark & Evaluation Metrics Tab
  function renderBenchmarkView() {
    const report = state.data.benchmark;
    const meta = state.data.metadata;
    if (!report || !meta) return;

    const k5 = report.metrics_at_k['K=5'];

    const benchmarkGrid = document.getElementById('benchmarkMetricsGrid');
    if (benchmarkGrid) {
      benchmarkGrid.innerHTML = `
        <div class="kpi-item" style="background: white; border: 1px solid #E2E8F0; padding: 18px; border-radius: 16px;">
          <div style="font-size: 12px; font-weight: 700; color: #64748B;">PRECISION @ K=5</div>
          <div style="font-size: 32px; font-weight: 800; color: #7C3AED; margin: 4px 0;">${(k5.precision * 100).toFixed(1)}%</div>
          <div style="font-size: 12px; color: #475569;">Hits: ${k5.hits} / 5 | NDCG: ${k5.ndcg}</div>
        </div>

        <div class="kpi-item" style="background: white; border: 1px solid #E2E8F0; padding: 18px; border-radius: 16px;">
          <div style="font-size: 12px; font-weight: 700; color: #64748B;">BOUNDARY START MAE</div>
          <div style="font-size: 32px; font-weight: 800; color: #10B981; margin: 4px 0;">${report.boundary_mae.start_seconds_mae}s</div>
          <div style="font-size: 12px; color: #475569;">Sub-2 second speech boundary lock</div>
        </div>

        <div class="kpi-item" style="background: white; border: 1px solid #E2E8F0; padding: 18px; border-radius: 16px;">
          <div style="font-size: 12px; font-weight: 700; color: #64748B;">BOUNDARY END MAE</div>
          <div style="font-size: 32px; font-weight: 800; color: #2563EB; margin: 4px 0;">${report.boundary_mae.end_seconds_mae}s</div>
          <div style="font-size: 12px; color: #475569;">Zero-error cut on narrative cliffhanger</div>
        </div>

        <div class="kpi-item" style="background: white; border: 1px solid #E2E8F0; padding: 18px; border-radius: 16px;">
          <div style="font-size: 12px; font-weight: 700; color: #64748B;">RECALL @ K=5 / TOTAL GT</div>
          <div style="font-size: 32px; font-weight: 800; color: #F43F5E; margin: 4px 0;">${(k5.recall * 100).toFixed(1)}%</div>
          <div style="font-size: 12px; color: #475569;">Evaluated against 20 ground truth promos</div>
        </div>
      `;
    }

    // Populate Evaluation Metric Matrix Table (K=5, K=10, K=20, K=30)
    const matrixTableBody = document.getElementById('benchmarkMatrixTableBody');
    if (matrixTableBody) {
      const keys = ['K=5', 'K=10', 'K=20', 'K=30'];
      let matrixHtml = '';
      keys.forEach(k => {
        const m = report.metrics_at_k[k];
        if (!m) return;
        matrixHtml += `
          <tr>
            <td style="font-weight: 800; color: #7C3AED;">${k}</td>
            <td style="font-weight: 700;">${(m.precision * 100).toFixed(1)}%</td>
            <td style="font-weight: 700;">${(m.recall * 100).toFixed(1)}%</td>
            <td style="font-weight: 700; color: #2563EB;">${m.ndcg.toFixed(3)}</td>
            <td style="font-weight: 700;">${m.hits} hits</td>
            <td style="font-size: 12px; color: #64748B;">Strict IoU &ge; 0.4 overlap against human golden standards</td>
          </tr>
        `;
      });
      matrixTableBody.innerHTML = matrixHtml;
    }
  }

  // 13. Editorial Review Hub View
  function renderEditorialHubView() {
    const tableBody = document.getElementById('editorialTableBody');
    if (!tableBody) return;

    const passed = state.data.passedCandidates || [];

    const filtered = passed.filter(p => {
      const decision = state.editorialDecisions[p.candidate_id]?.decision || 'PENDING';
      if (state.editorialStatusFilter === 'all') return true;
      return decision === state.editorialStatusFilter;
    });

    let html = '';
    filtered.forEach(p => {
      const rec = state.editorialDecisions[p.candidate_id];
      const decision = rec?.decision || 'PENDING';
      const notes = rec?.notes || '';

      let statusPill = `<span style="background: #F1F5F9; color: #64748B; padding: 4px 10px; border-radius: 99px; font-weight: 700; font-size: 11px;">PENDING</span>`;
      if (decision === 'APPROVED') {
        statusPill = `<span style="background: #D1FAE5; color: #065F46; padding: 4px 10px; border-radius: 99px; font-weight: 700; font-size: 11px;">✓ APPROVED</span>`;
      } else if (decision === 'RECUT') {
        statusPill = `<span style="background: #FEF3C7; color: #92400E; padding: 4px 10px; border-radius: 99px; font-weight: 700; font-size: 11px;">✎ RECUT NEEDED</span>`;
      } else if (decision === 'REJECTED') {
        statusPill = `<span style="background: #FFE4E6; color: #9F1239; padding: 4px 10px; border-radius: 99px; font-weight: 700; font-size: 11px;">✕ REJECTED</span>`;
      }

      html += `
        <tr>
          <td style="font-weight: 700;">#${p.rank || '-'}</td>
          <td><code style="background: #F1F5F9; padding: 2px 6px; border-radius: 4px; font-size: 11px;">${p.candidate_id}</code></td>
          <td><span class="ep-tag">EP ${p.episode_number}</span></td>
          <td style="font-weight: 600;">${escapeHtml(p.promo_title)}</td>
          <td>${p.duration_seconds}s</td>
          <td style="font-weight: 800; color: #7C3AED;">${p.final_score.toFixed(1)}</td>
          <td>${statusPill}</td>
          <td>
            <input type="text" class="editorial-note-input" placeholder="Add editorial note..." value="${escapeHtml(notes)}" onchange="window.DramaApp.saveNote('${p.candidate_id}', this.value)">
          </td>
          <td>
            <div style="display: flex; align-items: center; gap: 8px;">
              <button class="preview-btn" style="padding: 5px 10px; font-size: 11px;" onclick="window.DramaApp.selectAndPlay('${p.candidate_id}')" title="Play in Phone Player">▶</button>
              <div class="editorial-btn-group">
                <button class="editorial-btn approve ${decision === 'APPROVED' ? 'active' : ''}" title="Approve Promo" onclick="window.DramaApp.markEditorial('${p.candidate_id}', 'APPROVED')">✓</button>
                <button class="editorial-btn recut ${decision === 'RECUT' ? 'active' : ''}" title="Request Recut" onclick="window.DramaApp.markEditorial('${p.candidate_id}', 'RECUT')">✎</button>
                <button class="editorial-btn reject ${decision === 'REJECTED' ? 'active' : ''}" title="Reject Promo" onclick="window.DramaApp.markEditorial('${p.candidate_id}', 'REJECTED')">✕</button>
              </div>
            </div>
          </td>
        </tr>
      `;
    });

    tableBody.innerHTML = html || `<tr><td colspan="9" style="text-align: center; padding: 32px; color: #64748B;">No promos match status "${state.editorialStatusFilter}".</td></tr>`;
  }

  // 14. Export Editorial Feedback to CSV (with UTF-8 BOM for Excel)
  function exportEditorialCsv() {
    const candidates = state.data.passedCandidates || [];
    let csv = '\uFEFFcandidate_id,episode_number,rank,decision,reviewer_name,notes,timestamp\n';

    candidates.forEach(c => {
      const record = state.editorialDecisions[c.candidate_id];
      const decision = record?.decision || 'PENDING';
      const reviewer = record ? 'Lead AI Editor' : '';
      const notes = (record?.notes || '').replace(/"/g, '""');
      const time = record?.timestamp || '';
      csv += `${c.candidate_id},${c.episode_number},${c.rank || 0},${decision},"${reviewer}","${notes}",${time}\n`;
    });

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `human_feedback_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast('Editorial feedback exported successfully as production CSV!');
  }

  // 15. Lightbox Modal Controller with Zoom-In / Zoom-Out & Pan
  function openLightbox(candidateId) {
    state.zoom.level = 1.0;
    state.zoom.panX = 0;
    state.zoom.panY = 0;
    applyZoom();

    const backdrop = document.getElementById('lightboxModal');
    const img = document.getElementById('lightboxImage');
    const title = document.getElementById('modalTitle');
    const epBadge = document.getElementById('modalEpBadge');
    const scoreBadge = document.getElementById('modalScoreBadge');
    const openQuote = document.getElementById('modalOpenQuote');
    const closeQuote = document.getElementById('modalCloseQuote');
    const transcriptList = document.getElementById('modalTranscriptList');
    const playBtn = document.getElementById('modalPlayInPhoneBtn');

    if (candidateId === 'series_poster') {
      // Series Key Art Spotlight Mode
      if (img) img.src = state.data.seriesInfo.poster;
      if (title) title.innerText = state.data.seriesInfo.title;
      if (epBadge) epBadge.innerText = 'OFFICIAL KEY ART POSTER • 50 EPISODES';
      if (scoreBadge) scoreBadge.innerText = 'Series Key Art Spotlight';
      if (openQuote) openQuote.innerText = 'Publicly humiliated and betrayed at the altar when her groom chooses her sister, Lady Juliana makes a defiant wager.';
      if (closeQuote) closeQuote.innerText = 'Alexander, legendary war hero and Duke of Rochester, hunting traitors in disguise.';

      if (transcriptList) {
        let charHtml = `
          <div style="background: #F8FAFC; padding: 14px; border-radius: 12px; margin-bottom: 12px; border-left: 3px solid #7C3AED;">
            <div style="font-weight: 700; font-size: 13px; color: #0F172A; margin-bottom: 4px;">Series Synopsis</div>
            <div style="font-size: 12px; color: #475569; line-height: 1.5;">${state.data.seriesInfo.synopsis}</div>
          </div>
          <h5 style="font-size: 12px; font-weight: 700; color: #64748B; margin-bottom: 8px;">Main Drama Characters:</h5>
        `;
        (state.data.seriesInfo.characters || []).forEach(ch => {
          charHtml += `
            <div class="event-line-item dialogue" style="margin-bottom: 6px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <img src="${ch.avatar}" style="width: 28px; height: 28px; border-radius: 50%; object-fit: cover;" alt="${ch.name}">
                <div>
                  <div style="font-weight: 700; font-size: 12px; color: #0F172A;">${ch.name} <span style="font-weight: 500; font-size: 11px; color: #7C3AED;">(${ch.title})</span></div>
                  <div style="font-size: 11px; color: #64748B;">${ch.desc}</div>
                </div>
              </div>
            </div>
          `;
        });
        transcriptList.innerHTML = charHtml;
      }

      if (playBtn) {
        playBtn.onclick = () => {
          closeLightbox();
          window.DramaApp.selectAndPlay(state.data.top5[0].candidate_id);
        };
      }
    } else {
      // Candidate promo mode
      const promo = state.data.allCandidates.find(c => c.candidate_id === candidateId);
      if (!promo) return;

      if (img) img.src = promo.scene_image;
      if (title) title.innerText = promo.promo_title;
      if (epBadge) epBadge.innerText = `EPISODE ${promo.episode_number} (${promo.start_display} - ${promo.end_display}) • ${promo.duration_seconds}s`;
      if (scoreBadge) scoreBadge.innerText = `Score: ${promo.final_score.toFixed(1)} / 10`;
      if (openQuote) openQuote.innerText = promo.opening_quote;
      if (closeQuote) closeQuote.innerText = promo.closing_quote;

      if (transcriptList) {
        let eventsHtml = '';
        (promo.events_summary || []).forEach(ev => {
          let typeClass = 'event-line-item';
          if (ev.includes('DIALOGUE')) typeClass += ' dialogue';
          else if (ev.includes('CAMERA')) typeClass += ' camera';
          else if (ev.includes('ACTION')) typeClass += ' action';

          eventsHtml += `
            <div class="${typeClass}">
              <div class="event-content-text">${escapeHtml(ev)}</div>
            </div>
          `;
        });
        transcriptList.innerHTML = eventsHtml || '<div style="color: #64748B; font-size: 13px;">No event lines recorded.</div>';
      }

      if (playBtn) {
        playBtn.onclick = () => {
          closeLightbox();
          window.DramaApp.selectAndPlay(candidateId);
        };
      }
    }

    if (backdrop) backdrop.classList.add('open');
  }

  function closeLightbox() {
    const backdrop = document.getElementById('lightboxModal');
    if (backdrop) backdrop.classList.remove('open');
  }

  function zoomIn() {
    state.zoom.level = Math.min(state.zoom.max, Number((state.zoom.level + state.zoom.step).toFixed(2)));
    applyZoom();
  }

  function zoomOut() {
    state.zoom.level = Math.max(state.zoom.min, Number((state.zoom.level - state.zoom.step).toFixed(2)));
    if (state.zoom.level <= 1.0) {
      state.zoom.panX = 0;
      state.zoom.panY = 0;
    }
    applyZoom();
  }

  function resetZoom() {
    state.zoom.level = 1.0;
    state.zoom.panX = 0;
    state.zoom.panY = 0;
    applyZoom();
  }

  function applyZoom() {
    const img = document.getElementById('lightboxImage');
    const text = document.getElementById('zoomLevelText');
    const stage = document.querySelector('.modal-visual-stage');

    if (img) {
      img.style.transform = `translate(${state.zoom.panX}px, ${state.zoom.panY}px) scale(${state.zoom.level})`;
    }
    if (text) {
      text.innerText = `${Math.round(state.zoom.level * 100)}%`;
    }
    if (stage) {
      if (state.zoom.level > 1.0) {
        stage.classList.add('can-pan');
      } else {
        stage.classList.remove('can-pan', 'panning');
      }
    }
  }

  // 16. Event Bindings
  function bindEvents() {
    // Nav Tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        state.activeTab = btn.getAttribute('data-tab');
        renderActiveTab();
      });
    });

    // View Mode Switcher
    document.querySelectorAll('.mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.viewMode = btn.getAttribute('data-mode');
        renderActiveTab();
      });
    });

    // Search Input
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        state.searchQuery = e.target.value.trim();
        renderActiveTab();
      });
    }

    // Episode Filter
    const epSelect = document.getElementById('episodeSelect');
    if (epSelect) {
      epSelect.addEventListener('change', (e) => {
        state.selectedEpisode = e.target.value;
        renderActiveTab();
      });
    }

    // Min Score Filter
    const scoreRange = document.getElementById('scoreRange');
    const scoreVal = document.getElementById('scoreValueDisplay');
    if (scoreRange) {
      scoreRange.addEventListener('input', (e) => {
        state.minScore = parseFloat(e.target.value);
        if (scoreVal) scoreVal.innerText = `${state.minScore.toFixed(1)}+`;
        renderActiveTab();
      });
    }

    // Duration Filter
    const durSelect = document.getElementById('durationSelect');
    if (durSelect) {
      durSelect.addEventListener('change', (e) => {
        state.durationFilter = e.target.value;
        renderActiveTab();
      });
    }

    // Verdict Filter
    const verdictSelect = document.getElementById('verdictSelect');
    if (verdictSelect) {
      verdictSelect.addEventListener('change', (e) => {
        state.verdictFilter = e.target.value;
        renderActiveTab();
      });
    }

    // Sort By
    const sortSelect = document.getElementById('sortSelect');
    if (sortSelect) {
      sortSelect.addEventListener('change', (e) => {
        state.sortBy = e.target.value;
        renderActiveTab();
      });
    }

    // Radar Tab Candidate Selector
    const radarPromoSelect = document.getElementById('radarPromoSelect');
    if (radarPromoSelect) {
      radarPromoSelect.addEventListener('change', (e) => {
        state.radarPromoId = e.target.value;
        renderRadarView();
      });
    }

    // Radar vs Bar Comparison Switchers
    const radarModeWebBtn = document.getElementById('radarModeWebBtn');
    const radarModeBarBtn = document.getElementById('radarModeBarBtn');
    if (radarModeWebBtn && radarModeBarBtn) {
      radarModeWebBtn.addEventListener('click', () => {
        radarModeWebBtn.classList.add('active');
        radarModeBarBtn.classList.remove('active');
        state.chartMode = 'radar';
        if (state.radarEngine) state.radarEngine.setMode('radar');
      });
      radarModeBarBtn.addEventListener('click', () => {
        radarModeBarBtn.classList.add('active');
        radarModeWebBtn.classList.remove('active');
        state.chartMode = 'bars';
        if (state.radarEngine) state.radarEngine.setMode('bars');
      });
    }

    const radarPlayCurrentBtn = document.getElementById('radarPlayCurrentBtn');
    if (radarPlayCurrentBtn) {
      radarPlayCurrentBtn.addEventListener('click', () => {
        const id = state.radarPromoId || state.activePromo?.candidate_id;
        if (id) {
          window.DramaApp.selectAndPlay(id);
          state.activeTab = 'showcase';
          renderActiveTab();
        }
      });
    }

    // Audit Tab Filters
    const auditGateFilter = document.getElementById('auditGateFilter');
    if (auditGateFilter) {
      auditGateFilter.addEventListener('change', (e) => {
        state.auditGateFilter = e.target.value;
        renderAuditView();
      });
    }
    const auditEpSelect = document.getElementById('auditEpisodeSelect');
    if (auditEpSelect) {
      auditEpSelect.addEventListener('change', (e) => {
        state.auditEpisodeFilter = e.target.value;
        renderAuditView();
      });
    }
    const auditSearchInput = document.getElementById('auditSearchInput');
    if (auditSearchInput) {
      auditSearchInput.addEventListener('input', (e) => {
        state.auditSearchQuery = e.target.value.trim();
        renderAuditView();
      });
    }

    // Editorial Tab Status Filter Pills
    document.querySelectorAll('.editorial-filter-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        document.querySelectorAll('.editorial-filter-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        state.editorialStatusFilter = pill.getAttribute('data-ed-filter') || 'all';
        renderEditorialHubView();
      });
    });

    // Export CSV Button
    const exportBtn = document.getElementById('exportFeedbackBtn');
    if (exportBtn) {
      exportBtn.addEventListener('click', exportEditorialCsv);
    }

    // Phone Play Button
    const playBtn = document.getElementById('phonePlayBtn');
    if (playBtn) {
      playBtn.addEventListener('click', togglePlayback);
    }

    // Phone Mute Button
    const muteBtn = document.getElementById('phoneMuteBtn');
    if (muteBtn) {
      muteBtn.addEventListener('click', () => {
        if (!state.audioEngine) return;
        const isMuted = state.audioEngine.toggleMute();
        muteBtn.innerText = isMuted ? '🔇' : '🔊';
      });
    }

    // Interactive Scrubber with Click & Mouse/Touch Drag
    setupInteractiveScrubber();

    // Like Button
    const likeBtn = document.getElementById('phoneLikeBtn');
    if (likeBtn) {
      likeBtn.addEventListener('click', () => {
        const id = state.activePromo?.candidate_id;
        if (!id) return;
        state.socialLikes[id] = (state.socialLikes[id] || 12400) + 1;
        updatePhonePreview();
      });
    }

    // Zoom Controls in Lightbox
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const zoomResetBtn = document.getElementById('zoomResetBtn');
    const modalCloseBtn = document.getElementById('modalCloseBtn');
    const modalBackdrop = document.getElementById('lightboxModal');

    if (zoomInBtn) zoomInBtn.addEventListener('click', zoomIn);
    if (zoomOutBtn) zoomOutBtn.addEventListener('click', zoomOut);
    if (zoomResetBtn) zoomResetBtn.addEventListener('click', resetZoom);
    if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeLightbox);
    if (modalBackdrop) {
      modalBackdrop.addEventListener('click', (e) => {
        if (e.target === modalBackdrop) closeLightbox();
      });
    }

    // Interactive Wheel Zoom & Pan Drag inside Lightbox
    setupLightboxZoomAndPan();

    // Keyboard ESC to close modal, Space to toggle playback
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeLightbox();
      if (e.key === ' ' && e.target === document.body) {
        e.preventDefault();
        togglePlayback();
      }
    });
  }

  // Interactive Scrubber Drag Implementation
  function setupInteractiveScrubber() {
    const scrubber = document.getElementById('timelineScrubber');
    if (!scrubber) return;

    function handleSeekFromEvent(e) {
      const rect = scrubber.getBoundingClientRect();
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      seekPlayback(pct * state.playback.duration);
    }

    // Click seek
    scrubber.addEventListener('click', (e) => {
      handleSeekFromEvent(e);
    });

    // Mouse drag
    scrubber.addEventListener('mousedown', (e) => {
      state.playback.isDraggingScrubber = true;
      handleSeekFromEvent(e);

      function onMouseMove(moveEvent) {
        if (!state.playback.isDraggingScrubber) return;
        handleSeekFromEvent(moveEvent);
      }

      function onMouseUp() {
        state.playback.isDraggingScrubber = false;
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
      }

      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
    });

    // Touch drag (mobile)
    scrubber.addEventListener('touchstart', (e) => {
      state.playback.isDraggingScrubber = true;
      handleSeekFromEvent(e);

      function onTouchMove(moveEvent) {
        if (!state.playback.isDraggingScrubber) return;
        handleSeekFromEvent(moveEvent);
      }

      function onTouchEnd() {
        state.playback.isDraggingScrubber = false;
        window.removeEventListener('touchmove', onTouchMove);
        window.removeEventListener('touchend', onTouchEnd);
      }

      window.addEventListener('touchmove', onTouchMove);
      window.addEventListener('touchend', onTouchEnd);
    }, { passive: true });
  }

  // Lightbox Wheel-Zoom & Mouse Pan Drag Implementation
  function setupLightboxZoomAndPan() {
    const stage = document.querySelector('.modal-visual-stage');
    const img = document.getElementById('lightboxImage');
    if (!stage || !img) return;

    // Wheel zoom
    stage.addEventListener('wheel', (e) => {
      e.preventDefault();
      if (e.deltaY < 0) {
        zoomIn();
      } else {
        zoomOut();
      }
    }, { passive: false });

    // Double-click toggle zoom (100% <-> 200%)
    img.addEventListener('dblclick', () => {
      if (state.zoom.level > 1.2) {
        resetZoom();
      } else {
        state.zoom.level = 2.0;
        applyZoom();
      }
    });

    // Mouse Pan Drag
    stage.addEventListener('mousedown', (e) => {
      if (state.zoom.level <= 1.0) return;
      state.zoom.isPanning = true;
      state.zoom.startX = e.clientX - state.zoom.panX;
      state.zoom.startY = e.clientY - state.zoom.panY;
      stage.classList.add('panning');

      function onMouseMove(moveEvent) {
        if (!state.zoom.isPanning) return;
        state.zoom.panX = moveEvent.clientX - state.zoom.startX;
        state.zoom.panY = moveEvent.clientY - state.zoom.startY;
        applyZoom();
      }

      function onMouseUp() {
        state.zoom.isPanning = false;
        stage.classList.remove('panning');
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
      }

      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
    });
  }

  function resetFilters() {
    state.searchQuery = '';
    state.selectedEpisode = 'all';
    state.minScore = 5.0;
    state.durationFilter = 'all';
    state.verdictFilter = 'all';
    state.sortBy = 'rank';

    const searchInput = document.getElementById('searchInput');
    const epSelect = document.getElementById('episodeSelect');
    const scoreRange = document.getElementById('scoreRange');
    const scoreVal = document.getElementById('scoreValueDisplay');
    const durSelect = document.getElementById('durationSelect');
    const verdictSelect = document.getElementById('verdictSelect');
    const sortSelect = document.getElementById('sortSelect');

    if (searchInput) searchInput.value = '';
    if (epSelect) epSelect.value = 'all';
    if (scoreRange) scoreRange.value = 5.0;
    if (scoreVal) scoreVal.innerText = '5.0+';
    if (durSelect) durSelect.value = 'all';
    if (verdictSelect) verdictSelect.value = 'all';
    if (sortSelect) sortSelect.value = 'rank';

    renderActiveTab();
  }

  // 17. Toast Notifications
  function showToast(msg) {
    let toast = document.getElementById('appToast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'appToast';
      toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        background: #0F172A;
        color: white;
        padding: 12px 20px;
        border-radius: 99px;
        font-size: 13px;
        font-weight: 600;
        box-shadow: 0 10px 25px -5px rgba(0,0,0,0.3);
        z-index: 9999;
        display: flex;
        align-items: center;
        gap: 8px;
        opacity: 0;
        transform: translateY(20px);
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        pointer-events: none;
      `;
      document.body.appendChild(toast);
    }
    toast.innerHTML = `<span>✨</span> ${escapeHtml(msg)}`;
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(20px)';
    }, 2800);
  }

  // Helpers
  function formatTime(seconds) {
    const s = Math.floor(seconds);
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return `${m < 10 ? '0' : ''}${m}:${rem < 10 ? '0' : ''}${rem}`;
  }

  function formatK(num) {
    if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
    return num.toString();
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Expose global controller
  window.DramaApp = {
    selectAndPlay: (id) => {
      const promo = state.data.allCandidates.find(c => c.candidate_id === id);
      if (promo) {
        state.activePromo = promo;
        state.radarPromoId = id;

        // Toggle .active class across DOM cards
        document.querySelectorAll('.promo-card').forEach(card => {
          if (card.getAttribute('data-id') === id) {
            card.classList.add('active');
          } else {
            card.classList.remove('active');
          }
        });

        // Update dropdown if in radar tab
        const select = document.getElementById('radarPromoSelect');
        if (select) select.value = id;

        updatePhonePreview();
        startPlayback();

        // On mobile, smoothly scroll toward phone simulator
        if (window.innerWidth <= 1120) {
          document.getElementById('phoneSimulatorBox')?.scrollIntoView({ behavior: 'smooth' });
        }
      }
    },
    onCardClick: (event, id) => {
      window.DramaApp.selectAndPlay(id);
    },
    markEditorial: (id, decision) => {
      saveEditorialDecision(id, decision);
    },
    saveNote: (id, text) => {
      saveEditorialNote(id, text);
    },
    openLightbox: (id) => {
      openLightbox(id);
    },
    closeLightbox: () => {
      closeLightbox();
    },
    setRadarPromo: (id) => {
      state.radarPromoId = id;
      renderRadarView();
    },
    exportCsv: () => {
      exportEditorialCsv();
    }
  };

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
