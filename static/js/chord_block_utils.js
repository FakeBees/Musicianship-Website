/**
 * chord_block_utils.js
 * Shared chord-block logic used by both harmonic.js and holistic.js.
 * Exposes everything via window.ChordBlockUtils = { ... }.
 */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Constants
  // ---------------------------------------------------------------------------

  const SHARP_NAMES = ['C','C♯','D','D♯','E','F','F♯','G','G♯','A','A♯','B'];
  const FLAT_NAMES  = ['C','D♭','D','E♭','E','F','G♭','G','A♭','A','B♭','B'];

  // Keys that prefer flat spellings
  const FLAT_KEYS = new Set(['F','Bb','Eb','Ab','Db','Gb','Dm','Gm','Cm','Fm']);

  function noteNameForPc(pc, keySignature) {
    return FLAT_KEYS.has(keySignature) ? FLAT_NAMES[pc] : SHARP_NAMES[pc];
  }

  // Diatonic scales: ordered array of 7 pitch classes starting from the tonic
  const DIATONIC_SCALES = {
    'C':  [0, 2, 4, 5, 7, 9, 11],
    'G':  [7, 9, 11, 0, 2, 4, 6],
    'D':  [2, 4, 6, 7, 9, 11, 1],
    'A':  [9, 11, 1, 2, 4, 6, 8],
    'E':  [4, 6, 8, 9, 11, 1, 3],
    'B':  [11, 1, 3, 4, 6, 8, 10],
    'F#': [6, 8, 10, 11, 1, 3, 5],
    'Gb': [6, 8, 10, 11, 1, 3, 5],
    'F':  [5, 7, 9, 10, 0, 2, 4],
    'Bb': [10, 0, 2, 3, 5, 7, 9],
    'Eb': [3, 5, 7, 8, 10, 0, 2],
    'Ab': [8, 10, 0, 1, 3, 5, 7],
    'Db': [1, 3, 5, 6, 8, 10, 0],
    // Minor (natural minor)
    'Am': [9, 11, 0, 2, 4, 5, 7],
    'Em': [4, 6, 7, 9, 11, 0, 2],
    'Bm': [11, 1, 2, 4, 6, 7, 9],
    'Dm': [2, 4, 5, 7, 9, 10, 0],
    'Gm': [7, 9, 10, 0, 2, 3, 5],
    'Cm': [0, 2, 3, 5, 7, 8, 10],
    'Fm': [5, 7, 8, 10, 0, 1, 3],
  };

  // Triad qualities for each diatonic degree in major / minor keys
  const DIATONIC_QUALITIES_MAJOR = ['major','minor','minor','major','major','minor','diminished'];
  const DIATONIC_QUALITIES_MINOR = ['minor','diminished','major','minor','minor','major','major'];

  // Interval patterns (intervals above root in semitones)
  const QUALITY_INTERVALS = {
    major:      [0, 4, 7],
    minor:      [0, 3, 7],
    diminished: [0, 3, 6],
    augmented:  [0, 4, 8],
  };

  // I–IV–V–I (major) and i–iv–V–i (minor) reference voicings per key
  const HARM_KEY_REFERENCE = {
    'C':  [['C3','E4','G4','C5'], ['F3','F4','A4','C5'], ['G3','G4','B4','D5'],  ['C3','E4','G4','C5']],
    'G':  [['G2','B3','D4','G4'], ['C3','C4','E4','G4'], ['D3','D4','F#4','A4'], ['G2','B3','D4','G4']],
    'D':  [['D3','F#3','A3','D4'],['G3','G4','B4','D5'], ['A3','A4','C#5','E5'], ['D3','F#3','A3','D4']],
    'A':  [['A2','E3','A3','C#4'],['D3','D4','F#4','A4'],['E3','E4','G#4','B4'], ['A2','E3','A3','C#4']],
    'E':  [['E3','B3','E4','G#4'],['A3','A4','C#5','E5'],['B3','B4','D#5','F#5'],['E3','B3','E4','G#4']],
    'B':  [['B2','F#3','B3','D#4'],['E3','E4','G#4','B4'],['F#3','F#4','A#4','C#5'],['B2','F#3','B3','D#4']],
    'F#': [['F#2','C#3','F#3','A#3'],['B2','B3','D#4','F#4'],['C#3','C#4','F4','G#4'],['F#2','C#3','F#3','A#3']],
    'Gb': [['Gb2','Db3','Gb3','Bb3'],['Cb3','Cb4','Eb4','Gb4'],['Db3','Db4','F4','Ab4'],['Gb2','Db3','Gb3','Bb3']],
    'F':  [['F2','A3','C4','F4'],  ['Bb2','Bb3','D4','F4'], ['C3','C4','E4','G4'],  ['F2','A3','C4','F4']],
    'Bb': [['Bb2','D3','F3','Bb3'],['Eb3','Eb4','G4','Bb4'],['F3','F4','A4','C5'],  ['Bb2','D3','F3','Bb3']],
    'Eb': [['Eb3','G3','Bb3','Eb4'],['Ab3','Ab4','C5','Eb5'],['Bb3','Bb4','D5','F5'],['Eb3','G3','Bb3','Eb4']],
    'Ab': [['Ab2','Eb3','Ab3','C4'],['Db3','Db4','F4','Ab4'],['Eb3','Eb4','G4','Bb4'],['Ab2','Eb3','Ab3','C4']],
    'Db': [['Db3','F3','Ab3','Db4'],['Gb3','Gb4','Bb4','Db5'],['Ab3','Ab4','C5','Eb5'],['Db3','F3','Ab3','Db4']],
    // Minor: i – iv – V (major, raised 7th) – i
    'Am': [['A2','E4','A4','C5'], ['D3','F4','A4','D5'], ['E3','E4','G#4','B4'], ['A2','E4','A4','C5']],
    'Em': [['E3','B3','E4','G4'], ['A3','A4','C5','E5'], ['B3','B4','D#5','F#5'],['E3','B3','E4','G4']],
    'Bm': [['B2','F#3','B3','D4'],['E3','E4','G4','B4'], ['F#3','F#4','A#4','C#5'],['B2','F#3','B3','D4']],
    'Dm': [['D3','A3','D4','F4'], ['G3','G4','Bb4','D5'],['A3','A4','C#5','E5'], ['D3','A3','D4','F4']],
    'Gm': [['G2','D4','G4','Bb4'],['C3','C4','Eb4','G4'],['D3','D4','F#4','A4'], ['G2','D4','G4','Bb4']],
    'Cm': [['C3','G3','C4','Eb4'],['F3','F4','Ab4','C5'],['G3','G4','B4','D5'],  ['C3','G3','C4','Eb4']],
    'Fm': [['F2','C4','F4','Ab4'],['Bb2','Bb3','Db4','F4'],['C3','C4','E4','G4'],['F2','C4','F4','Ab4']],
  };

  // ---------------------------------------------------------------------------
  // Chord name helpers
  // ---------------------------------------------------------------------------

  function scaleDegreePc(pc, keySignature) {
    const scale = DIATONIC_SCALES[keySignature] || DIATONIC_SCALES['C'];
    const idx = scale.indexOf(pc);
    return idx >= 0 ? idx : null;
  }

  const ROMAN_UPPER = ['I','II','III','IV','V','VI','VII'];
  const ROMAN_LOWER = ['i','ii','iii','iv','v','vi','vii'];

  function extStr(exts) {
    if (!exts || !exts.length) return '';
    const order = ['b9','9','#9','11','#11','13','b13'];
    const sorted = [...exts].sort((a,b) => {
      const ai = order.indexOf(a); const bi = order.indexOf(b);
      return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi);
    });
    return sorted.map(e => e.replace('b','♭').replace('#','♯')).join('');
  }

  function formatChordName(chord, mode, keySignature) {
    if (!chord) return '?';
    const rootPc   = chord.root_pc   != null ? chord.root_pc   : 0;
    const rootName = (chord.root_name || 'C').replace('b','♭').replace('#','♯');
    const quality  = chord.quality   || 'major';
    const bassPc   = chord.bass_pc   != null ? chord.bass_pc   : rootPc;
    const bassName = (chord.bass_name || chord.root_name || 'C').replace('b','♭').replace('#','♯');
    const seventh  = chord.seventh   || null;
    const exts     = chord.extensions || [];
    const sus      = chord.sus       || null;

    const qualitySuffix = { major:'', minor:'m', diminished:'dim', augmented:'+' };

    function seventhSuf(quality, seventh) {
      if (seventh === 'major7') return quality === 'major' ? 'maj7' : 'maj7';
      if (seventh === 'minor7') return quality === 'minor' ? 'm7' : '7';
      if (seventh === 'diminished7') return 'dim7';
      return '';
    }

    if (mode === 'lead') {
      let sym;
      if (sus) {
        sym = rootName + sus;
      } else if (seventh) {
        if (quality === 'diminished' && seventh === 'diminished7') {
          sym = rootName + 'dim7';
        } else if (quality === 'minor' && seventh === 'minor7') {
          sym = rootName + 'm7';
        } else if (quality === 'diminished' && seventh === 'minor7') {
          sym = rootName + 'm7♭5';
        } else {
          const qSuf = qualitySuffix[quality] || '';
          const sSuf = seventhSuf(quality, seventh);
          sym = rootName + qSuf + sSuf;
        }
      } else {
        sym = rootName + (qualitySuffix[quality] || '');
      }
      sym += extStr(exts);
      if (bassPc !== rootPc) sym += '/' + bassName;
      return sym;
    }

    // Roman or Nashville
    let degIdx = scaleDegreePc(rootPc, keySignature);
    let prefix = '';
    if (degIdx === null) {
      const flatPc   = (rootPc + 1) % 12;
      const sharpPc  = (rootPc - 1 + 12) % 12;
      const flatDeg  = scaleDegreePc(flatPc, keySignature);
      const sharpDeg = scaleDegreePc(sharpPc, keySignature);
      const preferSharp = chord.prefer_sharp;
      if (preferSharp === true && sharpDeg !== null)       { prefix = '♯'; degIdx = sharpDeg; }
      else if (preferSharp === false && flatDeg !== null)  { prefix = '♭'; degIdx = flatDeg;  }
      else if (flatDeg  !== null)                          { prefix = '♭'; degIdx = flatDeg;  }
      else if (sharpDeg !== null)                          { prefix = '♯'; degIdx = sharpDeg; }
      else                                                 { degIdx = 0; }
    }

    function numeral(degIdx, quality, prefix) {
      if (mode === 'roman') {
        const arr = (quality === 'minor' || quality === 'diminished') ? ROMAN_LOWER : ROMAN_UPPER;
        return prefix + arr[degIdx];
      } else {
        return prefix + String(degIdx + 1);
      }
    }

    let sym = numeral(degIdx, quality, prefix);

    if (sus) {
      sym += sus;
    } else if (seventh) {
      if (quality === 'diminished' && seventh === 'diminished7') {
        sym += '°⁷';
      } else if (quality === 'diminished' && seventh === 'minor7') {
        sym += 'ø⁷';
      } else if (seventh === 'major7') {
        sym += 'maj⁷';
      } else {
        sym += '⁷';
      }
    } else {
      if (quality === 'diminished') sym += '°';
      else if (quality === 'augmented') sym += '⁺';
      else if (quality === 'minor' && mode === 'nashville') sym += 'm';
    }
    sym += extStr(exts);

    if (bassPc !== rootPc) {
      if (mode === 'roman') {
        // Figured bass notation for Roman numeral mode
        const intervals = QUALITY_INTERVALS[quality] || [0, 4, 7];
        const sortedInts = [...intervals].sort((a, b) => a - b);
        const thirdPc  = sortedInts.length > 1 ? (rootPc + sortedInts[1]) % 12 : null;
        const fifthPc  = sortedInts.length > 2 ? (rootPc + sortedInts[2]) % 12 : null;
        let seventhPc  = null;
        if (seventh === 'major7')      seventhPc = (rootPc + 11) % 12;
        else if (seventh === 'minor7') seventhPc = (rootPc + 10) % 12;
        else if (seventh === 'diminished7') seventhPc = (rootPc + 9) % 12;
        if (bassPc === thirdPc)                       sym += '6';
        else if (bassPc === fifthPc)                  sym += '64';
        else if (seventhPc !== null && bassPc === seventhPc) sym += '4/2';
        else                                          sym += '/' + bassName;
      } else {
        // Nashville: slash with scale degree number
        const bassDeg = scaleDegreePc(bassPc, keySignature);
        sym += bassDeg !== null ? '/' + (bassDeg + 1) : '/' + bassName;
      }
    }
    return sym;
  }

  // ---------------------------------------------------------------------------
  // computeChordTones (was getChordTones in harmonic.js)
  // ---------------------------------------------------------------------------

  function computeChordTones(chord) {
    const intervals = QUALITY_INTERVALS[chord.quality] || [0, 4, 7];
    const tones = intervals.map(i => (chord.root_pc + i) % 12);
    if (chord.seventh === 'major7')      tones.push((chord.root_pc + 11) % 12);
    if (chord.seventh === 'minor7')      tones.push((chord.root_pc + 10) % 12);
    if (chord.seventh === 'diminished7') tones.push((chord.root_pc + 9)  % 12);
    return tones;
  }

  // ---------------------------------------------------------------------------
  // Expose public API
  // ---------------------------------------------------------------------------

  window.ChordBlockUtils = {
    SHARP_NAMES,
    FLAT_NAMES,
    FLAT_KEYS,
    noteNameForPc,
    DIATONIC_SCALES,
    DIATONIC_QUALITIES_MAJOR,
    DIATONIC_QUALITIES_MINOR,
    QUALITY_INTERVALS,
    HARM_KEY_REFERENCE,
    scaleDegreePc,
    ROMAN_UPPER,
    ROMAN_LOWER,
    extStr,
    formatChordName,
    computeChordTones,
  };

})();
