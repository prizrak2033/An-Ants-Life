// Colony audio: everything synthesized, no asset files.
//
// Two layers, on the same principle the chronicle follows. An ambient
// bed reports the colony's condition continuously - how busy it is, how
// stressed, whether something is at the door - and one-shot sounds mark
// events. Those one-shots are gated by the same significance model the
// text uses, because 82% of logged events are routine churn and a sound
// per forage delivery would be a machine gun rather than information.
"use strict";

// The mix lives in an_ants_life/config.py alongside the rest of the
// tuning and arrives from /audio-config. What follows are fallbacks that
// mirror it, so an unreachable or older server leaves the page audible
// rather than silent. Both objects are mutated in place by
// applyAudioConfig, never reassigned, because the mixer and the page
// hold references to them from load.
const AUDIO_LEVELS = {
  default_volume: 0.6,

  drone_base: 0.02,
  drone_per_pop: 0.02,
  drone_dead: 0.008,
  drone_pop_reference: 30,
  drone_cutoff_min: 160,
  drone_cutoff_range: 340,

  threat_level: 0.055,
  threat_lfo_depth: 0.05,
  threat_freq: 44,
  threat_lfo_freq: 1.6,

  chitter_level: 0.05,
  chitter_income_reference: 2.2,
  chitter_max_rate: 0.9,

  limiter_knee: 0.6,
  noise_crest_trim: 0.63,

  // Nothing may retrigger faster than this, per kind (seconds), and no
  // more than max_voices sound at once. A colony under sustained attack
  // would otherwise stack dozens of identical voices into mud.
  event_cooldown: 0.35,
  max_voices: 8,
};

// kind -> [voice, base frequency, seconds, level]
const AUDIO_EVENTS = {
  queen_hit:               ["thud",   70,  0.45, 0.85],
  emergency_raid:          ["noise", 320,  0.55, 0.70],
  emergency_famine_start:  ["fall",  420,  0.90, 0.45],
  emergency_famine_end:    ["rise",  330,  0.80, 0.40],
  ending:                  ["fall",  180,  2.40, 0.60],

  praetorian_raised:       ["chord", 392,  0.70, 0.34],
  milestone:               ["chord", 523,  0.90, 0.32],
  chapter_start:           ["bell",  494,  1.60, 0.30],
  chapter_end:             ["bell",  330,  1.60, 0.24],

  enemy_loot_recovered:    ["blip",  740,  0.20, 0.28],
  enemy_escape:            ["fall",  520,  0.40, 0.30],
  enemy_steal:             ["thud",  140,  0.22, 0.30],
  objective_claimed:       ["blip",  620,  0.16, 0.20],
  territory_expansion:     ["blip",  440,  0.16, 0.14],
  territory_border_incident: ["noise", 240, 0.25, 0.26],
  rally_called:            ["fall",  300,  0.55, 0.40],
  rally_ended:             ["rise",  300,  0.45, 0.28],
  directive_placed:        ["blip",  880,  0.12, 0.16],
  emergency_famine_reassign: ["blip", 300,  0.18, 0.18],
  policy_changed:          ["blip",  520,  0.10, 0.12],
};

/** Merge the server's mix over the fallbacks. Safe to call before or
 *  after a ColonyAudio exists; levels are read at use rather than
 *  captured, so a late reply still takes effect. The event table is
 *  replaced wholesale rather than merged - config is the authority on
 *  which kinds have a voice, and a kind dropped there should fall
 *  silent, not linger from the defaults. */
function applyAudioConfig(data) {
  if (!data) return;
  Object.assign(AUDIO_LEVELS, data.levels || {});
  if (data.events) {
    for (const k of Object.keys(AUDIO_EVENTS)) delete AUDIO_EVENTS[k];
    Object.assign(AUDIO_EVENTS, data.events);
  }
}

class ColonyAudio {
  constructor() {
    this.ctx = null;
    this.enabled = false;
    this.volume = AUDIO_LEVELS.default_volume;
    this.lastPlayed = new Map();
    this.voices = 0;
    this._chitterTimer = null;
    this._state = { activity: 0, stress: 0, threat: 0, alive: false };
  }

  get ready() { return this.ctx !== null && this.ctx.state === "running"; }

  // Browsers refuse to start audio without a user gesture, so this is
  // called from a click rather than at load.
  async enable() {
    if (!this.ctx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return false;
      this.ctx = new Ctx();
      this._buildAmbience();
    }
    if (this.ctx.state === "suspended") await this.ctx.resume();
    this.enabled = true;
    this.master.gain.setTargetAtTime(this.volume, this.ctx.currentTime, 0.3);
    this._startChitter();
    return true;
  }

  disable() {
    this.enabled = false;
    if (!this.ctx) return;
    this.master.gain.setTargetAtTime(0.0, this.ctx.currentTime, 0.2);
    this._stopChitter();
  }

  setVolume(v) {
    this.volume = Math.max(0, Math.min(1, v));
    if (this.ctx && this.enabled) {
      this.master.gain.setTargetAtTime(this.volume, this.ctx.currentTime, 0.1);
    }
  }

  // ---------- ambience ----------

  _buildAmbience() {
    const ctx = this.ctx;
    this.master = ctx.createGain();
    this.master.gain.value = 0;
    this.master.connect(ctx.destination);

    // A safety ceiling for when several events land together, not a
    // levelling compressor: a single sound should arrive at exactly the
    // loudness it asked for.
    //
    // This was a DynamicsCompressor and no setting of it behaved. At
    // threshold -1dB with a hard knee, a blip of amplitude 0.12 - some
    // 60x below where it should have been ignored entirely - still came
    // out at 0.031, and its peak moved 6ms later. Measured against the
    // same voice with the node bypassed (0.1147 for a requested 0.12),
    // the compressor was costing 11dB and all of the dynamics.
    //
    // A shaping curve does the actual job. It is stateless, has no
    // lookahead, and is the identity below KNEE so one event passes
    // through at exactly its designed level, bending only as stacked
    // voices approach full scale - the one moment a ceiling was wanted.
    //
    // Note the curve's domain: a WaveShaper maps an input of -1..1 onto
    // the whole array, so the array has to be built over that range and
    // nothing else. Writing a plain tanh over -3..3 here turned the node
    // into a 3x drive stage instead, and every voice came out 2.8x too
    // loud. Input past +-1 clamps to the endpoints, which is what makes
    // the ceiling hold.
    this.limiter = ctx.createWaveShaper();
    const n = 2048, curve = new Float32Array(n);
    const knee = AUDIO_LEVELS.limiter_knee;
    for (let i = 0; i < n; i++) {
      const x = (i / (n - 1)) * 2 - 1;   // input range -1..1
      const a = Math.abs(x);
      curve[i] = a <= knee
        ? x
        : Math.sign(x) * (knee + (1 - knee) * Math.tanh((a - knee) / (1 - knee)));
    }
    this.limiter.curve = curve;
    this.limiter.oversample = "2x";
    this.limiter.connect(this.master);

    // Drone: three slightly detuned voices so it breathes instead of
    // sitting there as a test tone.
    this.droneGain = ctx.createGain();
    this.droneGain.gain.value = 0.0;
    this.droneFilter = ctx.createBiquadFilter();
    this.droneFilter.type = "lowpass";
    this.droneFilter.frequency.value = 300;
    this.droneFilter.Q.value = 2;
    this.droneGain.connect(this.droneFilter);
    this.droneFilter.connect(this.limiter);

    this.droneOscs = [];
    for (const [freq, detune] of [[55, -4], [55, 5], [82.5, 2]]) {
      const o = ctx.createOscillator();
      o.type = "triangle";
      o.frequency.value = freq;
      o.detune.value = detune;
      o.connect(this.droneGain);
      o.start();
      this.droneOscs.push(o);
    }

    // Threat pulse: a slow throb that only appears when something is
    // near the nest, so danger is audible without looking.
    //
    // The LFO's depth has to be driven from the threat level, not left
    // at a fixed value. An oscillator connected to an AudioParam *sums*
    // into it rather than scaling it, so a fixed depth of 0.5 against a
    // base gain of 0.0 means the 44Hz tone plays at half amplitude
    // forever, at every threat level including none. That was audible as
    // a constant floor under everything and it swamped the event voices:
    // measured RMS sat at ~0.25 for every one of them regardless of the
    // gain they asked for. Depth and base both scale with threat, so at
    // threat 0 the branch is genuinely silent.
    this.threatGain = ctx.createGain();
    this.threatGain.gain.value = 0.0;
    const threatOsc = ctx.createOscillator();
    threatOsc.type = "sine";
    threatOsc.frequency.value = AUDIO_LEVELS.threat_freq;
    const lfo = ctx.createOscillator();
    lfo.type = "sine";
    lfo.frequency.value = AUDIO_LEVELS.threat_lfo_freq;
    this.threatLfoDepth = ctx.createGain();
    this.threatLfoDepth.gain.value = 0.0;
    lfo.connect(this.threatLfoDepth);
    this.threatLfoDepth.connect(this.threatGain.gain);
    threatOsc.connect(this.threatGain);
    this.threatGain.connect(this.limiter);
    threatOsc.start();
    lfo.start();

    this.noiseBuffer = this._makeNoise(2.0);
  }

  _makeNoise(seconds) {
    const ctx = this.ctx;
    const len = Math.floor(ctx.sampleRate * seconds);
    const buf = ctx.createBuffer(1, len, ctx.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    return buf;
  }

  // The colony's own sound: sparse dry clicks whose rate follows how
  // much work is actually going on.
  _startChitter() {
    if (this._chitterTimer) return;
    const tick = () => {
      if (!this.enabled || !this.ctx) return;
      const s = this._state;
      if (s.alive && Math.random() < s.activity) this._click();
      const gap = 55 + Math.random() * 90;
      this._chitterTimer = setTimeout(tick, gap);
    };
    tick();
  }

  _stopChitter() {
    if (this._chitterTimer) clearTimeout(this._chitterTimer);
    this._chitterTimer = null;
  }

  _click() {
    const ctx = this.ctx;
    const src = ctx.createBufferSource();
    src.buffer = this.noiseBuffer;
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 1800 + Math.random() * 2200;
    bp.Q.value = 14;
    const g = ctx.createGain();
    const now = ctx.currentTime;
    g.gain.setValueAtTime(0.0, now);
    g.gain.linearRampToValueAtTime(AUDIO_LEVELS.chitter_level, now + 0.002);
    g.gain.exponentialRampToValueAtTime(0.0001, now + 0.05);
    src.connect(bp); bp.connect(g); g.connect(this.limiter);
    src.start(now);
    src.stop(now + 0.06);
  }

  /** Track colony condition. Called on every poll. */
  update(data) {
    this._state.alive = !data.game_over;
    // Delivery rate stands in for how busy the colony sounds.
    const income = (data.colony && data.colony.income_per_sec) || 0;
    this._state.activity = Math.max(0, Math.min(
      AUDIO_LEVELS.chitter_max_rate,
      income / AUDIO_LEVELS.chitter_income_reference));
    this._state.stress = (data.colony && data.colony.stress) || 0;

    const ec = data.enemy_counts || {};
    const enemies = (ec.WARRIOR || 0) + (ec.RAIDER || 0) + (ec.PREDATOR || 0);
    const bare = data.garrison && data.garrison.home === 0;
    this._state.threat = Math.min(1, enemies / 5 + (bare ? 0.5 : 0));

    if (!this.ready || !this.enabled) return;
    const now = this.ctx.currentTime;

    // Drone thins out as the colony does, and darkens under stress, so
    // a colony in trouble sounds like one without being told.
    const L = AUDIO_LEVELS;
    const pop = (data.colony && data.colony.population) || 0;
    const body = Math.min(1, pop / L.drone_pop_reference);
    this.droneGain.gain.setTargetAtTime(
      this._state.alive ? L.drone_base + L.drone_per_pop * body : L.drone_dead,
      now, 1.2);
    this.droneFilter.frequency.setTargetAtTime(
      L.drone_cutoff_min + L.drone_cutoff_range * (1 - this._state.stress),
      now, 1.5);
    // Base and modulation depth both track threat, so the throb swells
    // from silence rather than riding on a floor.
    const th = this._state.threat;
    this.threatGain.gain.setTargetAtTime(L.threat_level * th, now, 0.8);
    this.threatLfoDepth.gain.setTargetAtTime(L.threat_lfo_depth * th, now, 0.8);
  }

  /** One-shot for a story beat. */
  event(kind) {
    if (!this.ready || !this.enabled) return;
    const spec = AUDIO_EVENTS[kind];
    if (!spec) return;

    const now = this.ctx.currentTime;
    const last = this.lastPlayed.get(kind) || -99;
    if (now - last < AUDIO_LEVELS.event_cooldown) return;
    if (this.voices > AUDIO_LEVELS.max_voices) return;
    this.lastPlayed.set(kind, now);

    const [voice, freq, dur, gain] = spec;
    this.voices++;
    setTimeout(() => { this.voices--; }, dur * 1000);
    this._voice(voice, freq, dur, gain, now);
  }

  _voice(voice, freq, dur, gain, now) {
    const ctx = this.ctx;
    const g = ctx.createGain();
    g.connect(this.limiter);

    if (voice === "noise") {
      const src = ctx.createBufferSource();
      src.buffer = this.noiseBuffer;
      const bp = ctx.createBiquadFilter();
      bp.type = "bandpass";
      bp.frequency.value = freq;
      const q = 1.2;
      bp.Q.value = q;
      // A bandpass throws away everything outside its band, and white
      // noise spreads its power over the whole spectrum, so a band of
      // freq/Q Hz out of Nyquist survives - about 1% of the power at
      // 320Hz. Uncompensated, the raid alarm asked for the second
      // highest gain in the set and rendered as the second quietest
      // sound in it. Compensating by the band's share of the spectrum
      // puts a noise burst on the same scale as the tonal voices.
      // noise_crest_trim corrects for crest factor: matching a noise
      // burst to a sine on power alone overshoots on peak, because noise
      // peaks well above its RMS. Calibrated so a raid burst averages
      // level with a tonal voice of the same requested gain.
      //
      // Averages, not matches. The buffer is redrawn at random on every
      // build, and a burst's peak is an extreme value over a short
      // window, so measured peaks range about 1.33x across renders while
      // a tonal voice is identical every time. The trim centres that
      // spread and keeps its loud tail clear of full scale.
      const band = freq / q;
      const comp = AUDIO_LEVELS.noise_crest_trim
        * Math.min(14, Math.sqrt((ctx.sampleRate / 2) / band));
      src.connect(bp); bp.connect(g);
      g.gain.setValueAtTime(gain * comp, now);
      g.gain.exponentialRampToValueAtTime(0.0001, now + dur);
      src.start(now); src.stop(now + dur);
      return;
    }

    if (voice === "chord") {
      // A small triad, arpeggiated a touch so it reads as an event
      // rather than a chord stab.
      [1, 1.25, 1.5].forEach((mult, i) => {
        const o = ctx.createOscillator();
        const og = ctx.createGain();
        o.type = "sine";
        o.frequency.value = freq * mult;
        const start = now + i * 0.06;
        og.gain.setValueAtTime(0.0001, start);
        og.gain.exponentialRampToValueAtTime(gain / 2, start + 0.02);
        og.gain.exponentialRampToValueAtTime(0.0001, start + dur);
        o.connect(og); og.connect(this.limiter);
        o.start(start); o.stop(start + dur + 0.05);
      });
      return;
    }

    const o = ctx.createOscillator();
    o.connect(g);
    if (voice === "thud") {
      o.type = "sine";
      o.frequency.setValueAtTime(freq * 2.2, now);
      o.frequency.exponentialRampToValueAtTime(freq * 0.7, now + dur * 0.8);
    } else if (voice === "fall") {
      o.type = "triangle";
      o.frequency.setValueAtTime(freq, now);
      o.frequency.exponentialRampToValueAtTime(freq * 0.45, now + dur);
    } else if (voice === "rise") {
      o.type = "triangle";
      o.frequency.setValueAtTime(freq * 0.6, now);
      o.frequency.exponentialRampToValueAtTime(freq * 1.25, now + dur);
    } else if (voice === "bell") {
      o.type = "sine";
      o.frequency.value = freq;
    } else { // blip
      o.type = "square";
      o.frequency.value = freq;
    }

    g.gain.setValueAtTime(0.0001, now);
    g.gain.exponentialRampToValueAtTime(gain, now + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, now + dur);
    o.start(now);
    o.stop(now + dur + 0.05);
  }
}

window.ColonyAudio = ColonyAudio;
window.AUDIO_EVENTS = AUDIO_EVENTS;
window.AUDIO_LEVELS = AUDIO_LEVELS;
window.applyAudioConfig = applyAudioConfig;
