/**
 * player.js
 * Handles MIDI file loading and playback via Tone.js + @tonejs/midi.
 * Uses the Salamander Grand Piano sampler for realistic piano tone.
 */

(function () {
  'use strict';

  let sampler = null;
  let isPlaying = false;
  let playCount = 0;
  let scheduledEvents = [];

  const btnPlay  = document.getElementById('btn-play');
  const btnStop  = document.getElementById('btn-stop');
  const counter  = document.getElementById('play-count');

  // ---------------------------------------------------------------------------
  // Salamander Grand Piano sampler (Steinway Model B recordings)
  // Samples are fetched on first play; Tone.js interpolates between them.
  // ---------------------------------------------------------------------------
  function getSampler() {
    if (!sampler) {
      sampler = new Tone.Sampler({
        urls: {
          A0: 'A0.mp3',
          C1: 'C1.mp3', 'D#1': 'Ds1.mp3', 'F#1': 'Fs1.mp3', A1: 'A1.mp3',
          C2: 'C2.mp3', 'D#2': 'Ds2.mp3', 'F#2': 'Fs2.mp3', A2: 'A2.mp3',
          C3: 'C3.mp3', 'D#3': 'Ds3.mp3', 'F#3': 'Fs3.mp3', A3: 'A3.mp3',
          C4: 'C4.mp3', 'D#4': 'Ds4.mp3', 'F#4': 'Fs4.mp3', A4: 'A4.mp3',
          C5: 'C5.mp3', 'D#5': 'Ds5.mp3', 'F#5': 'Fs5.mp3', A5: 'A5.mp3',
          C6: 'C6.mp3', 'D#6': 'Ds6.mp3', 'F#6': 'Fs6.mp3', A6: 'A6.mp3',
          C7: 'C7.mp3', 'D#7': 'Ds7.mp3', 'F#7': 'Fs7.mp3', A7: 'A7.mp3',
          C8: 'C8.mp3',
        },
        release: 1.5,
        baseUrl: 'https://tonejs.github.io/audio/salamander/',
      }).toDestination();
    }
    return sampler;
  }

  async function play() {
    if (isPlaying) return;

    // Resume audio context on first user gesture (browser policy)
    await Tone.start();

    // Ensure sampler samples are loaded before scheduling
    getSampler();
    await Tone.loaded();

    try {
      const midi = await Midi.fromUrl(MIDI_URL);
      const s = getSampler();

      Tone.Transport.cancel();
      scheduledEvents = [];

      const now = Tone.Transport.seconds;

      midi.tracks.forEach((track) => {
        track.notes.forEach((note) => {
          const id = Tone.Transport.schedule((time) => {
            s.triggerAttackRelease(note.name, note.duration, time, note.velocity);
          }, now + note.time);
          scheduledEvents.push(id);
        });
      });

      // Compute end time so we can reset UI when playback finishes
      const totalDuration = midi.duration || 8;
      const endId = Tone.Transport.schedule(() => {
        resetUI();
      }, now + totalDuration + 0.5);
      scheduledEvents.push(endId);

      Tone.Transport.start();
      isPlaying = true;
      playCount++;
      if (counter) counter.textContent = `Plays: ${playCount}`;
      if (btnPlay) btnPlay.disabled = true;
      if (btnStop) btnStop.disabled = false;
    } catch (err) {
      console.error('Playback error:', err);
      alert('Could not load or play the MIDI file. See console for details.');
    }
  }

  function stop() {
    Tone.Transport.stop();
    Tone.Transport.cancel();
    scheduledEvents = [];
    resetUI();
  }

  function resetUI() {
    isPlaying = false;
    if (btnPlay) btnPlay.disabled = false;
    if (btnStop) btnStop.disabled = true;
  }

  // Expose play() publicly so exercise templates can chain it after references.
  // Templates are responsible for attaching their own btn-play listener.
  window.playMidi = play;
  if (btnStop) btnStop.addEventListener('click', stop);

  // -------------------------------------------------------------------------
  // Public: play an array of {key, duration} notes (used on results page)
  // -------------------------------------------------------------------------

  /** Convert VexFlow key like "c#/4" → Tone.js pitch like "C#4". */
  function vexKeyToTonePitch(key) {
    const parts = key.split('/');
    if (parts.length !== 2) return null;
    return parts[0].charAt(0).toUpperCase() + parts[0].slice(1) + parts[1];
  }

  /** Duration code → beats. */
  const DUR_BEATS = {
    w: 4, h: 2, q: 1, '8': 0.5, '16': 0.25,
    wr: 4, hr: 2, qr: 1, '8r': 0.5, '16r': 0.25,
  };

  /**
   * Play a note array through the sampler.
   * @param {Array}  notes  [{key, duration}, ...]
   * @param {number} bpm    tempo in BPM (default 100)
   * @param {function|null} onDone  callback when finished
   */
  // Timeout handle for chord-array playback done callback.
  // Stored inside the IIFE so stopAllNotes can cancel it.
  let _chordDoneTimeout = null;

  /**
   * Stop all currently playing notes and cancel any pending chord-array playback.
   * Also stops the MIDI Transport so MIDI file playback is interrupted.
   */
  window.stopAllNotes = function () {
    if (typeof Tone === 'undefined') return;
    // Cancel MIDI Transport events
    Tone.Transport.stop();
    Tone.Transport.cancel();
    // Cancel any pending onDone callback
    if (_chordDoneTimeout !== null) {
      clearTimeout(_chordDoneTimeout);
      _chordDoneTimeout = null;
    }
    // Release all sampler voices
    try { getSampler().releaseAll(); } catch (e) { /* sampler not yet loaded */ }
  };

  /**
   * Play an array of chord voicings through the Salamander piano.
   * Uses direct AudioContext (Tone.now()) scheduling instead of Transport
   * to avoid timing glitches from Transport stop/start cycles.
   * @param {Array}  chords  [['C3','E4','G4','C5'], ...]  — one array of note names per chord
   * @param {number} bpm     tempo in BPM (default 72); each chord lasts 2 beats
   * @param {function|null} onDone  callback when finished
   */
  window.playChordArray = async function (chords, bpm, onDone) {
    if (typeof Tone === 'undefined') return;
    await Tone.start();
    // Stop any previous playback (MIDI Transport + sampler voices + pending callback)
    window.stopAllNotes();
    // Ensure sampler is initialized and samples are loaded
    getSampler();
    await Tone.loaded();
    const s = getSampler();
    const secPerBeat = 60 / (bpm || 72);
    const chordDur   = 2 * secPerBeat;
    // Schedule directly against AudioContext time — avoids Transport race conditions
    const startTime  = Tone.now() + 0.1;
    chords.forEach((noteNames, i) => {
      s.triggerAttackRelease(noteNames, chordDur - 0.05, startTime + i * chordDur, 0.8);
    });
    if (onDone) {
      const totalMs = (chords.length * chordDur + 0.3) * 1000;
      _chordDoneTimeout = setTimeout(() => {
        _chordDoneTimeout = null;
        onDone();
      }, totalMs);
    }
  };

  window.playNoteArray = async function (notes, bpm, onDone) {
    if (typeof Tone === 'undefined') return;
    await Tone.start();

    getSampler();
    await Tone.loaded();

    const s = getSampler();
    Tone.Transport.cancel();
    const secPerBeat = 60 / (bpm || 100);
    let t = Tone.Transport.seconds;

    notes.forEach((n, idx) => {
      const baseBeats = DUR_BEATS[n.duration] || 1;
      const beats     = n.dotted ? baseBeats * 1.5 : baseBeats;
      const isRest    = n.duration.endsWith('r');

      // tieEnd: sound already covered by the tieStart note — advance clock silently.
      if (n.tieEnd) {
        t += beats * secPerBeat;
        return;
      }

      if (!isRest) {
        // For a tieStart, extend sound to cover the tied continuation.
        let soundBeats = beats;
        if (n.tieStart && idx + 1 < notes.length && notes[idx + 1].tieEnd) {
          const nxt = notes[idx + 1];
          const nb  = DUR_BEATS[nxt.duration] || 1;
          soundBeats += nxt.dotted ? nb * 1.5 : nb;
        }
        const pitch = vexKeyToTonePitch(n.key);
        if (pitch) {
          Tone.Transport.schedule((time) => {
            s.triggerAttackRelease(pitch, soundBeats * secPerBeat * 0.9, time);
          }, t);
        }
      }
      t += beats * secPerBeat;
    });

    if (onDone) {
      Tone.Transport.schedule(() => { onDone(); }, t + 0.3);
    }
    Tone.Transport.start();
  };

  /**
   * Play a metronome count-in: one measure of sine-click ticks.
   * Compound meters (6/8, 9/8, 12/8): beat = dotted quarter.
   * Simple meters: beat = quarter note.
   * @param {number}        bpm      tempo in BPM
   * @param {number}        top      time signature numerator
   * @param {number}        bot      time signature denominator
   * @param {function|null} onDone   callback when finished
   */
  window.playCountIn = async function (bpm, top, bot, onDone) {
    if (typeof Tone === 'undefined') return;
    await Tone.start();

    const synth = new Tone.Synth({
      oscillator: { type: 'sine' },
      envelope: { attack: 0.001, decay: 0.04, sustain: 0, release: 0.02 },
    }).toDestination();

    const secPerBeat  = 60 / (bpm || 100);
    const isCompound  = (bot === 8);
    const numBeats    = isCompound ? top / 3 : top;
    const beatSec     = isCompound ? secPerBeat * 1.5 : secPerBeat;

    Tone.Transport.cancel();
    let t = Tone.Transport.seconds;

    for (let i = 0; i < numBeats; i++) {
      const beatTime = t + i * beatSec;
      Tone.Transport.schedule(time => {
        synth.triggerAttackRelease('A5', '32n', time);
      }, beatTime);
    }

    if (onDone) {
      // Fire onDone exactly on the next beat — no buffer so WAV/next step starts in time
      Tone.Transport.schedule(() => { onDone(); }, t + numBeats * beatSec);
    }
    Tone.Transport.start();
  };

  /**
   * Play a count-in measure then the MIDI file in one seamless Transport session.
   * Count-in ticks and MIDI notes are scheduled together (same approach as
   * playRhythmArray) so the MIDI starts on the exact beat with no gap.
   * @param {number} bpm   tempo in BPM
   * @param {number} top   time signature numerator
   * @param {number} bot   time signature denominator
   */
  window.playMidiWithCountIn = async function (bpm, top, bot) {
    if (isPlaying) return;

    await Tone.start();
    getSampler();
    await Tone.loaded();
    const s = getSampler();

    try {
      // Load MIDI file (browser-cached after first play, so effectively instant)
      const midi = await Midi.fromUrl(MIDI_URL);

      const synth = new Tone.Synth({
        oscillator: { type: 'sine' },
        envelope:   { attack: 0.001, decay: 0.04, sustain: 0, release: 0.02 },
      }).toDestination();

      const secPerBeat = 60 / (bpm || 100);
      const isCompound = (bot === 8);
      const numBeats   = isCompound ? top / 3 : top;
      const beatSec    = isCompound ? secPerBeat * 1.5 : secPerBeat;

      // Single Transport session — position advances through count-in then MIDI
      Tone.Transport.cancel();
      scheduledEvents = [];
      let t = 0; // schedule from the start of the Transport

      // Count-in clicks
      for (let i = 0; i < numBeats; i++) {
        Tone.Transport.schedule(time => {
          synth.triggerAttackRelease('A5', '32n', time);
        }, t + i * beatSec);
      }
      t += numBeats * beatSec; // t now points to the first beat of the exercise

      // MIDI notes — seamlessly following the count-in
      midi.tracks.forEach(track => {
        track.notes.forEach(note => {
          const id = Tone.Transport.schedule(time => {
            s.triggerAttackRelease(note.name, note.duration, time, note.velocity);
          }, t + note.time);
          scheduledEvents.push(id);
        });
      });

      // UI reset when MIDI finishes
      const totalDuration = midi.duration || 8;
      const endId = Tone.Transport.schedule(() => { resetUI(); }, t + totalDuration + 0.5);
      scheduledEvents.push(endId);

      // Start Transport from the beginning
      Tone.Transport.stop();
      Tone.Transport.start();
      isPlaying = true;
      playCount++;
      if (counter) counter.textContent = `Plays: ${playCount}`;
      if (btnPlay) btnPlay.disabled = true;
      if (btnStop) btnStop.disabled = false;
    } catch (err) {
      console.error('Playback error:', err);
      alert('Could not load or play the MIDI file. See console for details.');
    }
  };
})();
