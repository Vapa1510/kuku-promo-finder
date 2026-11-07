/**
 * Web Audio API Cinematic Procedural Synthesizer & Soundscape Engine
 * Simulates dramatic vertical drama audio preview:
 * - Sub-bass drone & cello undertone
 * - Ambient mid/high presence for full visualizer frequency coverage
 * - Rhythmic heartbeat / clock pulse with auto-disconnect
 * - Rising cliffhanger riser with safe exponential ramp bounds
 * - Animated audio visualizer frequency analyzer
 */

class DramaAudioEngine {
  constructor() {
    this.ctx = null;
    this.isPlaying = false;
    this.isMuted = false;
    this.volume = 0.7;
    this.masterGain = null;
    this.analyser = null;
    this.nodes = [];
    this.pulseInterval = null;
    this.animationFrameId = null;
    this.onTick = null;
    this.onVisualizerUpdate = null;
    this.onStop = null;
  }

  init() {
    if (this.ctx) return;
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) {
        console.warn('Web Audio API not supported in this browser.');
        return;
      }
      this.ctx = new AudioContext();
      this.masterGain = this.ctx.createGain();
      this.masterGain.gain.setValueAtTime(this.volume, this.ctx.currentTime);

      this.analyser = this.ctx.createAnalyser();
      this.analyser.fftSize = 128;
      this.analyser.smoothingTimeConstant = 0.75;

      this.masterGain.connect(this.analyser);
      this.analyser.connect(this.ctx.destination);
    } catch (e) {
      console.warn('Failed to initialize AudioContext', e);
    }
  }

  start(durationSeconds = 40) {
    this.init();
    if (!this.ctx) return;
    if (this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {});
    }
    this.stop();

    this.isPlaying = true;
    const now = this.ctx.currentTime;
    const dur = Math.max(0.6, durationSeconds);

    // Guaranteed strictly increasing timestamps for audio parameter scheduling
    const attackEnd = Math.min(1.5, dur * 0.25);
    const releaseStart = Math.max(attackEnd + 0.05, dur - Math.min(2.5, dur * 0.35));

    // 1. Deep Sub-bass Cinematic Drone (Root note: C2 ~ 65.4Hz)
    const droneOsc = this.ctx.createOscillator();
    const droneGain = this.ctx.createGain();
    droneOsc.type = 'sawtooth';
    droneOsc.frequency.setValueAtTime(65.41, now);

    const filter = this.ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.setValueAtTime(220, now);
    filter.frequency.exponentialRampToValueAtTime(520, now + dur);

    droneGain.gain.setValueAtTime(0.001, now);
    droneGain.gain.linearRampToValueAtTime(0.24, now + attackEnd);
    droneGain.gain.setValueAtTime(0.24, now + releaseStart);
    droneGain.gain.exponentialRampToValueAtTime(0.001, now + dur);

    droneOsc.connect(filter);
    filter.connect(droneGain);
    droneGain.connect(this.masterGain);
    droneOsc.start(now);
    droneOsc.stop(now + dur);
    this.nodes.push(droneOsc, droneGain, filter);

    // 2. Harmonic Cello 5th (G2 ~ 98.0Hz)
    const fifthOsc = this.ctx.createOscillator();
    const fifthGain = this.ctx.createGain();
    fifthOsc.type = 'triangle';
    fifthOsc.frequency.setValueAtTime(97.99, now);

    fifthGain.gain.setValueAtTime(0.001, now);
    fifthGain.gain.linearRampToValueAtTime(0.18, now + attackEnd + 0.05);
    fifthGain.gain.setValueAtTime(0.18, now + releaseStart);
    fifthGain.gain.exponentialRampToValueAtTime(0.001, now + dur);

    fifthOsc.connect(fifthGain);
    fifthGain.connect(this.masterGain);
    fifthOsc.start(now);
    fifthOsc.stop(now + dur);
    this.nodes.push(fifthOsc, fifthGain);

    // 3. Ambient Mid Presence for rich acoustic texture and full visualizer spread
    const airOsc = this.ctx.createOscillator();
    const airGain = this.ctx.createGain();
    const airFilter = this.ctx.createBiquadFilter();
    airOsc.type = 'sine';
    airOsc.frequency.setValueAtTime(329.63, now); // E4 tone
    airFilter.type = 'bandpass';
    airFilter.frequency.setValueAtTime(440, now);

    airGain.gain.setValueAtTime(0.001, now);
    airGain.gain.linearRampToValueAtTime(0.06, now + attackEnd);
    airGain.gain.setValueAtTime(0.06, now + releaseStart);
    airGain.gain.exponentialRampToValueAtTime(0.001, now + dur);

    airOsc.connect(airFilter);
    airFilter.connect(airGain);
    airGain.connect(this.masterGain);
    airOsc.start(now);
    airOsc.stop(now + dur);
    this.nodes.push(airOsc, airFilter, airGain);

    // 4. Heartbeat / Clock Pulse generator
    const pulseRateMs = 850; // ~70 BPM dramatic heartbeat
    this.pulseInterval = setInterval(() => {
      if (!this.isPlaying || !this.ctx) return;
      this.triggerHeartbeat();
    }, pulseRateMs);

    // 5. Cliffhanger Riser (swells dramatically toward end if clip duration allows)
    if (dur > 2.0) {
      const riserStart = Math.max(attackEnd, dur - 3.5);
      const riserPeak = Math.max(riserStart + 0.3, dur - 0.2);
      const riserOsc = this.ctx.createOscillator();
      const riserGain = this.ctx.createGain();
      riserOsc.type = 'sine';
      riserOsc.frequency.setValueAtTime(180, now + riserStart);
      riserOsc.frequency.exponentialRampToValueAtTime(880, now + dur);

      riserGain.gain.setValueAtTime(0.0001, now + riserStart);
      riserGain.gain.exponentialRampToValueAtTime(0.32, now + riserPeak);
      riserGain.gain.linearRampToValueAtTime(0.0001, now + dur);

      riserOsc.connect(riserGain);
      riserGain.connect(this.masterGain);
      riserOsc.start(now + riserStart);
      riserOsc.stop(now + dur);
      this.nodes.push(riserOsc, riserGain);
    }

    // Start visualizer loop
    this.startVisualizer();
  }

  triggerHeartbeat() {
    if (!this.ctx || this.isMuted) return;
    const t = this.ctx.currentTime;

    // Low thud (lub)
    const osc1 = this.ctx.createOscillator();
    const gain1 = this.ctx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(75, t);
    osc1.frequency.exponentialRampToValueAtTime(35, t + 0.12);

    gain1.gain.setValueAtTime(0.3, t);
    gain1.gain.exponentialRampToValueAtTime(0.001, t + 0.12);

    osc1.connect(gain1);
    gain1.connect(this.masterGain);
    osc1.start(t);
    osc1.stop(t + 0.13);
    osc1.onended = () => {
      try {
        osc1.disconnect();
        gain1.disconnect();
      } catch (e) {}
    };

    // Second thud (dub)
    const t2 = t + 0.14;
    const osc2 = this.ctx.createOscillator();
    const gain2 = this.ctx.createGain();
    osc2.type = 'sine';
    osc2.frequency.setValueAtTime(65, t2);
    osc2.frequency.exponentialRampToValueAtTime(30, t2 + 0.15);

    gain2.gain.setValueAtTime(0.2, t2);
    gain2.gain.exponentialRampToValueAtTime(0.001, t2 + 0.15);

    osc2.connect(gain2);
    gain2.connect(this.masterGain);
    osc2.start(t2);
    osc2.stop(t2 + 0.16);
    osc2.onended = () => {
      try {
        osc2.disconnect();
        gain2.disconnect();
      } catch (e) {}
    };
  }

  startVisualizer() {
    if (!this.analyser) return;
    const bufferLength = this.analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const update = () => {
      if (!this.isPlaying) return;
      this.analyser.getByteFrequencyData(dataArray);
      if (this.onVisualizerUpdate) {
        this.onVisualizerUpdate(dataArray);
      }
      this.animationFrameId = requestAnimationFrame(update);
    };
    update();
  }

  stop() {
    this.isPlaying = false;
    if (this.pulseInterval) {
      clearInterval(this.pulseInterval);
      this.pulseInterval = null;
    }
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
    this.nodes.forEach(n => {
      try {
        if (typeof n.stop === 'function') n.stop();
        if (typeof n.disconnect === 'function') n.disconnect();
      } catch (e) {}
    });
    this.nodes = [];
    if (this.onStop) {
      this.onStop();
    }
  }

  toggleMute() {
    this.isMuted = !this.isMuted;
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.setValueAtTime(this.isMuted ? 0 : this.volume, this.ctx.currentTime);
    }
    return this.isMuted;
  }

  setVolume(val) {
    this.volume = Math.max(0, Math.min(1, val));
    if (this.masterGain && this.ctx && !this.isMuted) {
      this.masterGain.gain.setValueAtTime(this.volume, this.ctx.currentTime);
    }
  }
}

if (typeof window !== 'undefined') {
  window.DramaAudioEngine = DramaAudioEngine;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { DramaAudioEngine };
}
