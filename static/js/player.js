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

  if (btnPlay) btnPlay.addEventListener('click', play);
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
  window.playNoteArray = async function (notes, bpm, onDone) {
    if (typeof Tone === 'undefined') return;
    await Tone.start();

    getSampler();
    await Tone.loaded();

    const s = getSampler();
    Tone.Transport.cancel();
    const secPerBeat = 60 / (bpm || 100);
    let t = Tone.Transport.seconds;

    notes.forEach((n) => {
      const baseBeats = DUR_BEATS[n.duration] || 1;
      const beats  = n.dotted ? baseBeats * 1.5 : baseBeats;
      const isRest = n.duration.endsWith('r');
      if (!isRest) {
        const pitch = vexKeyToTonePitch(n.key);
        if (pitch) {
          Tone.Transport.schedule((time) => {
            s.triggerAttackRelease(pitch, beats * secPerBeat * 0.9, time);
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
})();
