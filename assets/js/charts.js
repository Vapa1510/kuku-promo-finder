/**
 * Interactive SVG Radar & Bar Comparison Chart Engine
 * Supports 7 core dimensions:
 * 1. Hook Strength (20%)
 * 2. Cliffhanger Strength (20%)
 * 3. Narrative Clarity (15%)
 * 4. Conflict & Stakes (15%)
 * 5. Emotional Pull (10%)
 * 6. Script Visual Potential (10%)
 * 7. Boundary Suitability (10%)
 */

class RadarChartEngine {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    this.options = Object.assign({
      width: 440,
      height: 400,
      maxValue: 10,
      levels: 5,
      color: '#7C3AED',
      compareColor: '#10B981',
      showLabels: true
    }, options);

    this.mode = 'radar'; // 'radar' | 'bars'
    this.currentScores = {};
    this.compareScores = null;
    this.currentTitle = 'Selected Promo';
    this.compareTitle = 'Benchmark Average';

    this.dimensions = [
      { key: 'hook_strength', label: 'Hook Strength', weight: '20%', desc: 'Opening 0-3s retention trigger' },
      { key: 'cliffhanger_strength', label: 'Cliffhanger', weight: '20%', desc: 'Final 3s climax and narrative crisis' },
      { key: 'narrative_clarity', label: 'Narrative Clarity', weight: '15%', desc: 'Standalone story comprehensibility' },
      { key: 'conflict_and_stakes', label: 'Conflict & Stakes', weight: '15%', desc: 'Betrayal and high emotional stakes' },
      { key: 'emotional_pull', label: 'Emotional Pull', weight: '10%', desc: 'Empathy with Juliana and Alexander' },
      { key: 'script_visual_potential', label: 'Visual Potential', weight: '10%', desc: 'Cinematic cues, swordplay, candles' },
      { key: 'boundary_suitability', label: 'Boundary Fit', weight: '10%', desc: 'Speech event cut precision' }
    ];
  }

  setMode(mode) {
    if (mode === 'radar' || mode === 'bars') {
      this.mode = mode;
      this.render(this.currentScores, this.compareScores, this.currentTitle, this.compareTitle);
    }
  }

  render(currentScores, compareScores = null, currentTitle = 'Selected Promo', compareTitle = 'Benchmark Average') {
    if (!this.container) return;

    this.currentScores = currentScores || {};
    this.compareScores = compareScores;
    this.currentTitle = currentTitle;
    this.compareTitle = compareTitle;

    if (this.mode === 'bars') {
      this.renderBarChart();
    } else {
      this.renderRadarChart();
    }
  }

  renderRadarChart() {
    const { width, height, maxValue, levels, compareColor } = this.options;
    const centerX = width / 2;
    const centerY = (height / 2) + 8;
    const radius = Math.min(centerX, centerY) - 62;
    const angleSlice = (Math.PI * 2) / this.dimensions.length;

    // Helper: calculate coordinates
    const getCoordinates = (value, index) => {
      const angle = index * angleSlice - Math.PI / 2;
      const r = (value / maxValue) * radius;
      return {
        x: centerX + r * Math.cos(angle),
        y: centerY + r * Math.sin(angle)
      };
    };

    // Header Title
    const titleSvg = `
      <text x="${centerX}" y="22" text-anchor="middle" fill="#0F172A" font-size="13" font-weight="700">
        ${this.escapeXml(this.currentTitle.length > 36 ? this.currentTitle.slice(0, 36) + '...' : this.currentTitle)}
      </text>
    `;

    // Build SVG web/grid levels
    let gridSvg = '';
    for (let level = 1; level <= levels; level++) {
      const levelFactor = (radius / levels) * level;
      const levelValue = (maxValue / levels) * level;
      let points = [];
      for (let i = 0; i < this.dimensions.length; i++) {
        const angle = i * angleSlice - Math.PI / 2;
        const x = centerX + levelFactor * Math.cos(angle);
        const y = centerY + levelFactor * Math.sin(angle);
        points.push(`${x.toFixed(1)},${y.toFixed(1)}`);
      }
      gridSvg += `<polygon points="${points.join(' ')}" fill="none" stroke="#E2E8F0" stroke-width="1.2" stroke-dasharray="${level < levels ? '2 2' : 'none'}" />`;
      gridSvg += `<text x="${centerX + 6}" y="${(centerY - levelFactor + 3).toFixed(1)}" fill="#94A3B8" font-size="10" font-weight="600">${levelValue.toFixed(0)}</text>`;
    }

    // Build radial axes and dimension labels
    let axesSvg = '';
    let labelsSvg = '';
    this.dimensions.forEach((dim, i) => {
      const angle = i * angleSlice - Math.PI / 2;
      const outerX = centerX + radius * Math.cos(angle);
      const outerY = centerY + radius * Math.sin(angle);
      axesSvg += `<line x1="${centerX}" y1="${centerY}" x2="${outerX.toFixed(1)}" y2="${outerY.toFixed(1)}" stroke="#E2E8F0" stroke-width="1.2" />`;

      const labelRadius = radius + 25;
      const labelX = centerX + labelRadius * Math.cos(angle);
      const labelY = centerY + labelRadius * Math.sin(angle);

      let textAnchor = 'middle';
      if (Math.cos(angle) > 0.25) textAnchor = 'start';
      else if (Math.cos(angle) < -0.25) textAnchor = 'end';

      const curVal = this.currentScores[dim.key] !== undefined ? this.currentScores[dim.key] : 8.0;

      labelsSvg += `
        <g class="radar-label-group" style="cursor: pointer;">
          <text x="${labelX.toFixed(1)}" y="${labelY.toFixed(1)}" text-anchor="${textAnchor}" fill="#0F172A" font-size="11" font-weight="700">${dim.label}</text>
          <text x="${labelX.toFixed(1)}" y="${(labelY + 11).toFixed(1)}" text-anchor="${textAnchor}" fill="#6D28D9" font-size="10" font-weight="700">${curVal} / 10</text>
        </g>
      `;
    });

    // Optional Compare Polygon (Benchmark Average)
    let comparePolygonSvg = '';
    if (this.compareScores) {
      const comparePoints = [];
      const compareCircles = [];
      this.dimensions.forEach((dim, i) => {
        const val = Math.max(0, Math.min(maxValue, this.compareScores[dim.key] || 7.5));
        const pt = getCoordinates(val, i);
        comparePoints.push(`${pt.x.toFixed(1)},${pt.y.toFixed(1)}`);
        compareCircles.push(`
          <circle cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="3.5" fill="${compareColor}" stroke="#FFFFFF" stroke-width="1.5">
            <title>${this.compareTitle} - ${dim.label}: ${val}/10</title>
          </circle>
        `);
      });

      comparePolygonSvg = `
        <g class="compare-layer">
          <polygon points="${comparePoints.join(' ')}" fill="${compareColor}" fill-opacity="0.14" stroke="${compareColor}" stroke-width="2" stroke-dasharray="4 3" />
          ${compareCircles.join('')}
        </g>
      `;
    }

    // Build Current Polygon
    const currentPoints = [];
    const currentCircles = [];
    this.dimensions.forEach((dim, i) => {
      const val = Math.max(0, Math.min(maxValue, this.currentScores[dim.key] || 8.0));
      const pt = getCoordinates(val, i);
      currentPoints.push(`${pt.x.toFixed(1)},${pt.y.toFixed(1)}`);
      currentCircles.push(`
        <circle cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="5" fill="#7C3AED" stroke="#FFFFFF" stroke-width="2" style="cursor: pointer; transition: transform 0.2s;">
          <title>${dim.label}: ${val} / 10 (${dim.weight} weight)</title>
        </circle>
      `);
    });

    const svg = `
      <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: auto; max-width: 440px; margin: 0 auto; display: block; user-select: none;">
        <defs>
          <linearGradient id="radarCurrentGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#7C3AED" stop-opacity="0.45" />
            <stop offset="100%" stop-color="#F43F5E" stop-opacity="0.25" />
          </linearGradient>
        </defs>
        ${titleSvg}
        ${gridSvg}
        ${axesSvg}
        ${comparePolygonSvg}
        <g class="current-layer">
          <polygon points="${currentPoints.join(' ')}" fill="url(#radarCurrentGrad)" stroke="#7C3AED" stroke-width="2.5" />
          ${currentCircles.join('')}
        </g>
        ${labelsSvg}
      </svg>
    `;

    this.container.innerHTML = svg;
  }

  renderBarChart() {
    const { width, maxValue } = this.options;
    const height = 400;

    let barsHtml = '';
    this.dimensions.forEach(dim => {
      const curVal = this.currentScores[dim.key] !== undefined ? this.currentScores[dim.key] : 8.0;
      const benchVal = this.compareScores ? (this.compareScores[dim.key] || 8.0) : 8.0;
      const curPct = Math.min(100, (curVal / maxValue) * 100);
      const benchPct = Math.min(100, (benchVal / maxValue) * 100);
      const delta = (curVal - benchVal).toFixed(1);
      const deltaSign = curVal >= benchVal ? `+${delta}` : delta;
      const deltaClass = curVal >= benchVal ? 'color: #059669;' : 'color: #D97706;';

      barsHtml += `
        <div style="display: flex; flex-direction: column; gap: 3px; margin-bottom: 12px;">
          <div style="display: flex; justify-content: space-between; font-size: 11.5px; font-weight: 700;">
            <span style="color: #0F172A;">${dim.label} <span style="font-weight: 500; color: #64748B;">(${dim.weight})</span></span>
            <span style="font-size: 11px;">
              <strong style="color: #7C3AED;">${curVal.toFixed(1)}</strong> vs <span style="color: #10B981;">${benchVal.toFixed(1)}</span>
              <span style="${deltaClass} margin-left: 4px;">(${deltaSign})</span>
            </span>
          </div>
          <!-- Selected promo bar -->
          <div style="width: 100%; height: 7px; background: #EDE9FE; border-radius: 4px; overflow: hidden;">
            <div style="width: ${curPct}%; height: 100%; background: linear-gradient(90deg, #7C3AED, #EC4899); border-radius: 4px;"></div>
          </div>
          <!-- Benchmark bar -->
          <div style="width: 100%; height: 5px; background: #D1FAE5; border-radius: 3px; overflow: hidden;">
            <div style="width: ${benchPct}%; height: 100%; background: #10B981; border-radius: 3px;"></div>
          </div>
        </div>
      `;
    });

    this.container.innerHTML = `
      <div style="width: 100%; max-width: 420px; padding: 12px 16px; background: #FFFFFF; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <div style="font-size: 13px; font-weight: 700; color: #0F172A; margin-bottom: 14px; text-align: center;">
          ${this.escapeXml(this.currentTitle.length > 38 ? this.currentTitle.slice(0, 38) + '...' : this.currentTitle)}
        </div>
        <div style="display: flex; justify-content: center; gap: 18px; margin-bottom: 12px; font-size: 11px; font-weight: 700;">
          <span style="display: flex; align-items: center; gap: 5px;">
            <span style="width: 10px; height: 10px; background: #7C3AED; border-radius: 2px;"></span>
            <span>Selected Clip</span>
          </span>
          <span style="display: flex; align-items: center; gap: 5px;">
            <span style="width: 10px; height: 10px; background: #10B981; border-radius: 2px;"></span>
            <span>Benchmark Avg</span>
          </span>
        </div>
        ${barsHtml}
      </div>
    `;
  }

  escapeXml(unsafe) {
    if (!unsafe) return '';
    return unsafe.replace(/[<>&'"]/g, c => {
      switch (c) {
        case '<': return '&lt;';
        case '>': return '&gt;';
        case '&': return '&amp;';
        case '\'': return '&apos;';
        case '"': return '&quot;';
      }
    });
  }
}

if (typeof window !== 'undefined') {
  window.RadarChartEngine = RadarChartEngine;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { RadarChartEngine };
}
