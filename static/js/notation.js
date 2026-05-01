/**
 * notation.js — VexFlow 4 notation editor for melodic dictation.
 *
 * Features: proportional note spacing, ghost-note hover preview (X+Y snapped),
 * dotted notes, 16th notes, rest placement via button/keyboard, drag-to-move,
 * key-signature-aware accidentals (auto-reset after use), keyboard shortcuts,
 * styled rendering (red highlights on results page).
 *
 * Keyboard shortcuts (exercise page):
 *   3 = 16th note   4 = eighth   5 = quarter   6 = half   7 = whole
 *   . = toggle dot  , = place rest   Ctrl+Z = undo
 */

(function () {
  'use strict';

  // =========================================================================
  // Layout constants
  // =========================================================================
  const MEASURES_PER_ROW = 4;
  const ROW_OFFSET  = 50;
  const ROW_HEIGHT  = 120;
  const STAVE_X_PAD = 15;
  const HALF_SPACE  = 5;
  const PROP_PAD    = 12;   // left padding within note area for proportional positioning

  const STEP_OFFSET = 4;

  // Per-clef note tables: index = step + STEP_OFFSET, from above-staff down.
  // Step 0 is the top staff line; each unit is one half-space (line or space).
  const NOTE_TABLES = {
    // Treble clef: top line = F5, bottom line = E4
    treble: [
      'c/6', 'b/5', 'a/5', 'g/5',
      'f/5', 'e/5', 'd/5', 'c/5', 'b/4',
      'a/4', 'g/4', 'f/4', 'e/4',
      'd/4', 'c/4', 'b/3', 'a/3',
    ],
    // Bass clef: top line = A3, bottom line = G2
    bass: [
      'e/4', 'd/4', 'c/4', 'b/3',
      'a/3', 'g/3', 'f/3', 'e/3', 'd/3',
      'c/3', 'b/2', 'a/2', 'g/2',
      'f/2', 'e/2', 'd/2', 'c/2',
    ],
    // Tenor clef (C clef on 4th line): top line = E4, bottom line = D3
    tenor: [
      'b/4', 'a/4', 'g/4', 'f/4',
      'e/4', 'd/4', 'c/4', 'b/3', 'a/3',
      'g/3', 'f/3', 'e/3', 'd/3',
      'c/3', 'b/2', 'a/2', 'g/2',
    ],
  };

  function getClef() {
    return (typeof CLEF !== 'undefined') ? CLEF : 'treble';
  }

  function getNoteTable() {
    return NOTE_TABLES[getClef()] || NOTE_TABLES.treble;
  }

  const DURATION_BEATS = {
    w: 4, h: 2, q: 1, '8': 0.5, '16': 0.25,
    wr: 4, hr: 2, qr: 1, '8r': 0.5, '16r': 0.25,
  };

  // Ghost note ellipse sizes per base duration
  const GHOST_SHAPES = {
    w:    { rx: 8,  ry: 5, fill: 'none',  stroke: '#555' },
    h:    { rx: 7,  ry: 5, fill: 'none',  stroke: '#555' },
    q:    { rx: 6,  ry: 4, fill: '#555',  stroke: '#555' },
    '8':  { rx: 6,  ry: 4, fill: '#555',  stroke: '#555' },
    '16': { rx: 5,  ry: 3, fill: '#555',  stroke: '#555' },
  };

  // =========================================================================
  // Key signature data
  // =========================================================================
  const KEY_SIG_ACCIDENTALS = {
    'C':  {},
    'G':  { f: '#' },
    'D':  { f: '#', c: '#' },
    'A':  { f: '#', c: '#', g: '#' },
    'E':  { f: '#', c: '#', g: '#', d: '#' },
    'B':  { f: '#', c: '#', g: '#', d: '#', a: '#' },
    'F#': { f: '#', c: '#', g: '#', d: '#', a: '#', e: '#' },
    'F':  { b: 'b' },
    'Bb': { b: 'b', e: 'b' },
    'Eb': { b: 'b', e: 'b', a: 'b' },
    'Ab': { b: 'b', e: 'b', a: 'b', d: 'b' },
    'Db': { b: 'b', e: 'b', a: 'b', d: 'b', g: 'b' },
    'Gb': { b: 'b', e: 'b', a: 'b', d: 'b', g: 'b', c: 'b' },
    // Minor keys (same accidentals as relative major)
    'Am': {},
    'Em': { f: '#' },
    'Bm': { f: '#', c: '#' },
    'Dm': { b: 'b' },
    'Gm': { b: 'b', e: 'b' },
    'Cm': { b: 'b', e: 'b', a: 'b' },
    'Fm': { b: 'b', e: 'b', a: 'b', d: 'b' },
  };

  function getKeySigAccidentals() {
    const keySig = (typeof KEY_SIGNATURE !== 'undefined') ? KEY_SIGNATURE : 'C';
    return KEY_SIG_ACCIDENTALS[keySig] || {};
  }

  /** Return the diatonic pitch for a base note in the current key. */
  function getDiatonicPitch(baseNote) {
    const slash  = baseNote.indexOf('/');
    const letter = baseNote.slice(0, slash);
    const octave = baseNote.slice(slash);
    const acc    = getKeySigAccidentals()[letter] || '';
    return letter + acc + octave;
  }

  /**
   * Apply raise/lower accidental relative to the diatonic pitch.
   * selectedAcc: '' (none), 'raise', 'lower'
   */
  function applyAccidental(baseNote) {
    const diatonic = getDiatonicPitch(baseNote);
    if (!selectedAcc) return diatonic;

    const slash      = diatonic.indexOf('/');
    const letterAcc  = diatonic.slice(0, slash);
    const octave     = diatonic.slice(slash);
    const letter     = letterAcc.charAt(0);
    const curAcc     = letterAcc.slice(1);  // '', '#', 'b', '##', 'bb'

    let newAcc;
    if (selectedAcc === 'raise') {
      if      (curAcc === '')   newAcc = '#';
      else if (curAcc === 'b')  newAcc = '';
      else if (curAcc === '#')  newAcc = '##';
      else if (curAcc === 'bb') newAcc = 'b';
      else                      newAcc = curAcc;
    } else {
      if      (curAcc === '')   newAcc = 'b';
      else if (curAcc === '#')  newAcc = '';
      else if (curAcc === 'b')  newAcc = 'bb';
      else if (curAcc === '##') newAcc = '#';
      else                      newAcc = curAcc;
    }
    return letter + newAcc + octave;
  }

  /**
   * Determine VexFlow accidental modifier to display for a note,
   * given the key signature alone. Returns null if no explicit accidental needed.
   */
  function getDisplayAccidental(noteKey) {
    const slash      = noteKey.indexOf('/');
    const letterAcc  = noteKey.slice(0, slash);
    const letter     = letterAcc.charAt(0);
    const noteAcc    = letterAcc.slice(1);
    const keyDefault = getKeySigAccidentals()[letter] || '';

    if (noteAcc === keyDefault) return null;
    if (noteAcc === '') return 'n';
    return noteAcc;
  }

  /**
   * Like getDisplayAccidental, but also tracks accidentals that occurred
   * earlier in the same measure (measureAccState). This handles cases like
   * C# → C♮ within a measure — the natural must be shown even though C is
   * the key-signature default.
   *
   * measureAccState is a plain object keyed by "letter+octave" (e.g. "c4").
   * It is mutated in place as notes are processed left-to-right.
   */
  function getDisplayAccidentalWithState(noteKey, measureAccState) {
    const slash      = noteKey.indexOf('/');
    const letterAcc  = noteKey.slice(0, slash);
    const octave     = noteKey.slice(slash + 1);
    const letter     = letterAcc.charAt(0);
    const noteAcc    = letterAcc.slice(1);
    const keyDefault = getKeySigAccidentals()[letter] || '';

    const stateKey   = letter + octave;
    // Effective accidental from earlier in this measure, or key-sig default
    const currentAcc = Object.prototype.hasOwnProperty.call(measureAccState, stateKey)
      ? measureAccState[stateKey]
      : keyDefault;

    // Record for subsequent notes in this measure
    measureAccState[stateKey] = noteAcc;

    if (noteAcc === currentAcc) return null;   // no change — nothing to display
    if (noteAcc === '') return 'n';            // natural cancels a prior accidental
    return noteAcc;                            // '#', 'b', '##', 'bb'
  }

  // =========================================================================
  // Editor state
  // =========================================================================
  let userNotes        = [];
  let selectedDur      = 'q';
  let selectedAcc      = '';      // '', 'raise', 'lower'
  let isDotted         = false;
  let currentBeats     = 0;
  let staveTopYs       = [];
  let measureInfo      = [];      // { startX, endX, noteStartX, noteWidth, staveY, usedBeats, isFull }
  let dragState        = null;
  let ghostEl          = null;
  let selectedNoteIdx  = null;    // index into userNotes of the tapped/selected note
  let pointerStartPos  = null;    // {x,y} recorded at interaction start
  let pendingDragTarget = null;   // potential drag before movement threshold is reached

  // =========================================================================
  // Pure helpers
  // =========================================================================

  function getBeatsPerMeasure() {
    const top = (typeof TIME_SIG_TOP    !== 'undefined') ? TIME_SIG_TOP    : 4;
    const bot = (typeof TIME_SIG_BOTTOM !== 'undefined') ? TIME_SIG_BOTTOM : 4;
    return top * (4 / bot);   // quarter-note beat units
  }

  function getTimeSigString() {
    if (typeof TIME_SIG_TOP !== 'undefined' && typeof TIME_SIG_BOTTOM !== 'undefined') {
      return `${TIME_SIG_TOP}/${TIME_SIG_BOTTOM}`;
    }
    return '4/4';
  }

  function getVoiceDef() {
    const top = (typeof TIME_SIG_TOP    !== 'undefined') ? TIME_SIG_TOP    : 4;
    const bot = (typeof TIME_SIG_BOTTOM !== 'undefined') ? TIME_SIG_BOTTOM : 4;
    return { num_beats: top, beat_value: bot };
  }

  /** Beats for a note object, accounting for dotted flag. */
  function noteBeats(n) {
    const base = DURATION_BEATS[n.duration] || 1;
    return n.dotted ? base * 1.5 : base;
  }

  /**
   * Convert a beat count to a {duration, dotted} spec.
   * Returns null if the value can't be expressed as a single standard note.
   * Used when splitting an overflowing note into a tied pair.
   */
  function beatsToNoteSpec(beats) {
    const table = [
      { beats: 4,     duration: 'w',  dotted: false },
      { beats: 3,     duration: 'h',  dotted: true  },
      { beats: 2,     duration: 'h',  dotted: false },
      { beats: 1.5,   duration: 'q',  dotted: true  },
      { beats: 1,     duration: 'q',  dotted: false },
      { beats: 0.75,  duration: '8',  dotted: true  },
      { beats: 0.5,   duration: '8',  dotted: false },
      { beats: 0.375, duration: '16', dotted: true  },
      { beats: 0.25,  duration: '16', dotted: false },
    ];
    for (const entry of table) {
      if (Math.abs(entry.beats - beats) < 0.001)
        return { duration: entry.duration, dotted: entry.dotted };
    }
    return null;
  }

  function stepFromY(clickY, staveY) {
    return Math.round((clickY - staveY) / HALF_SPACE);
  }

  function snappedY(step, staveY) {
    return staveY + step * HALF_SPACE;
  }

  function stepToNote(step) {
    const tbl  = getNoteTable();
    const idx  = step + STEP_OFFSET;
    if (idx < 0 || idx >= tbl.length) return null;
    return applyAccidental(tbl[idx]);
  }

  function yToNote(clickY, staveY) {
    return stepToNote(stepFromY(clickY, staveY));
  }

  function findStaveY(clickY) {
    for (const sy of staveTopYs) {
      if (clickY >= sy - 20 && clickY <= sy + 60) return sy;
    }
    return null;
  }

  /**
   * Find the measure index for a given (mx, clickY) position.
   * Filters by both X range and the matching stave row (Y), so that clicking
   * on row 2 col 0 returns a row-2 measure rather than the row-1 col-0 measure
   * that shares the same X range.
   */
  function findMeasure(mx, clickY) {
    const sy = findStaveY(clickY);
    if (sy === null) return -1;
    for (let i = 0; i < measureInfo.length; i++) {
      const m = measureInfo[i];
      if (mx >= m.startX && mx <= m.endX && m.staveY === sy) return i;
    }
    return -1;
  }

  /** Proportional X position for a note at beatOffset within a measure. */
  function propX(mInfo, beatOffset) {
    return mInfo.noteStartX + PROP_PAD + (beatOffset / getBeatsPerMeasure()) * mInfo.noteWidth;
  }

  function splitIntoMeasures(notes) {
    const measures = [];
    let cur = [], beats = 0;
    const bpm = getBeatsPerMeasure();
    for (const n of notes) {
      const b = noteBeats(n);
      if (beats + b > bpm + 0.001 && cur.length) {
        measures.push(cur); cur = []; beats = 0;
      }
      cur.push(n); beats += b;
    }
    if (cur.length) measures.push(cur);
    return measures;
  }

  /**
   * Build invisible GhostNote tickables to fill remaining beats in a measure.
   * Uses simple (non-dotted) durations to keep tick math straightforward.
   */
  function buildGhostPadding(usedBeats, VF) {
    let left = getBeatsPerMeasure() - usedBeats;
    if (left < 0.001) return [];
    const ghosts = [];
    const durMap = [
      { beats: 4,    dur: 'w'  },
      { beats: 2,    dur: 'h'  },
      { beats: 1,    dur: 'q'  },
      { beats: 0.5,  dur: '8'  },
      { beats: 0.25, dur: '16' },
    ];
    for (const { beats, dur } of durMap) {
      while (left >= beats - 0.001) {
        ghosts.push(new VF.GhostNote({ duration: dur }));
        left -= beats;
      }
    }
    return ghosts;
  }

  /**
   * Beat-aware beam builder.
   *
   * Groups consecutive beamable notes (8th, 16th) that fall within the same
   * beat. Uses noteBeats() from our own note data — which correctly accounts
   * for the dotted flag — instead of relying on VexFlow's internal tick system
   * (which is only correct after using the 'd' duration suffix).
   *
   * beatSize: 1.5 quarter-note units for compound meter (bot=8), else 1.0.
   */
  function buildBeams(mNotes, vfNotes, VF) {
    const bot      = (typeof TIME_SIG_BOTTOM !== 'undefined') ? TIME_SIG_BOTTOM : 4;
    const beatSize = (bot === 8) ? 1.5 : 1.0;
    const beams    = [];
    let pos        = 0;
    let groupNotes = [];
    let groupBeat  = -1;

    for (let i = 0; i < mNotes.length; i++) {
      const n          = mNotes[i];
      const b          = noteBeats(n);
      const isRest     = n.duration.endsWith('r');
      const isBeamable = !isRest && (n.duration === '8' || n.duration === '16');
      const beatNum    = Math.floor(pos / beatSize + 0.0001);

      if (isBeamable && beatNum === groupBeat) {
        groupNotes.push(vfNotes[i]);
      } else {
        if (groupNotes.length >= 2) {
          try { beams.push(new VF.Beam(groupNotes)); } catch (_) {}
        }
        groupNotes = isBeamable ? [vfNotes[i]] : [];
        groupBeat  = isBeamable ? beatNum : -1;
      }
      pos += b;
    }
    if (groupNotes.length >= 2) {
      try { beams.push(new VF.Beam(groupNotes)); } catch (_) {}
    }
    return beams;
  }

  /** Flash the notation SVG red to signal an error. */
  function flashError() {
    const svg = document.querySelector('#notation-container svg');
    if (svg) {
      svg.style.outline = '2px solid #dc3545';
      setTimeout(() => { svg.style.outline = ''; }, 500);
    }
  }

  // =========================================================================
  // VexFlow rendering
  // =========================================================================
  let VF;

  function initVexFlow() {
    if (typeof Vex === 'undefined') return 'VexFlow CDN did not load.';
    VF = Vex.Flow;
    if (!VF || !VF.Renderer) return 'Vex.Flow.Renderer missing.';
    return null;
  }

  /** Middle-of-staff rest key per clef (used so rests centre correctly). */
  function getRestKey() {
    switch (getClef()) {
      case 'bass':  return 'd/3';   // 3rd line of bass staff
      case 'tenor': return 'a/3';   // 3rd line of tenor staff
      default:      return 'b/4';   // 3rd line of treble staff
    }
  }

  function buildStaveNote(noteObj, style, measureAccState) {
    const isRest = noteObj.duration.endsWith('r');
    // Use 'd' suffix for dotted non-rests so VexFlow's tick count is correct
    // (addModifier(Dot) adds the visual dot but does NOT update internal ticks,
    //  which breaks Formatter spacing and beam-group detection).
    const vfDur = (noteObj.dotted && !isRest) ? noteObj.duration + 'd' : noteObj.duration;
    const sn = new VF.StaveNote({ keys: [noteObj.key], duration: vfDur, clef: getClef() });
    if (noteObj.dotted) sn.addModifier(new VF.Dot(), 0);
    if (!isRest) {
      const displayAcc = measureAccState
        ? getDisplayAccidentalWithState(noteObj.key, measureAccState)
        : getDisplayAccidental(noteObj.key);
      if (displayAcc) sn.addModifier(new VF.Accidental(displayAcc), 0);
    }
    if (style) sn.setStyle(style);
    return sn;
  }

  /**
   * Core render — draws all staves and applies proportional x positioning.
   */
  function renderStaves(containerEl, notes, numMeasures, interactive, styleMap) {
    containerEl.innerHTML = '';
    staveTopYs  = [];
    measureInfo = [];

    const totalWidth = containerEl.clientWidth || 800;
    const numRows    = Math.ceil(numMeasures / MEASURES_PER_ROW);
    const colCount   = Math.min(numMeasures, MEASURES_PER_ROW);
    const staveWidth = Math.max(120, Math.floor((totalWidth - STAVE_X_PAD * 2) / colCount));
    const svgHeight  = ROW_OFFSET + numRows * ROW_HEIGHT;
    const bpm        = getBeatsPerMeasure();

    const renderer = new VF.Renderer(containerEl, VF.Renderer.Backends.SVG);
    renderer.resize(totalWidth, svgHeight);
    const ctx = renderer.getContext();

    const keySig       = (typeof KEY_SIGNATURE !== 'undefined') ? KEY_SIGNATURE : 'C';
    const measureGroups = splitIntoMeasures(notes);
    while (measureGroups.length < numMeasures) measureGroups.push([]);

    let globalNoteIdx = 0;
    const tiesToDraw  = [];
    let   pendingTie  = null;  // { vfNote, row } — awaiting the tieEnd note in the next measure

    for (let i = 0; i < numMeasures; i++) {
      const row    = Math.floor(i / MEASURES_PER_ROW);
      const col    = i % MEASURES_PER_ROW;
      const staveY = ROW_OFFSET + row * ROW_HEIGHT;
      const staveX = STAVE_X_PAD + col * staveWidth;

      const stave = new VF.Stave(staveX, staveY, staveWidth);
      if (col === 0) stave.addClef(getClef());
      if (i   === 0) {
        if (keySig !== 'C') stave.addKeySignature(keySig);
        stave.addTimeSignature(getTimeSigString());
      }
      stave.setContext(ctx).draw();

      const topLineY   = stave.getYForLine(0);
      const noteStartX = stave.getNoteStartX();
      const noteEndX   = stave.getNoteEndX();
      const noteWidth  = Math.max(60, noteEndX - noteStartX - PROP_PAD * 2);

      staveTopYs.push(topLineY);

      const mNotes    = measureGroups[i];
      const usedBeats = mNotes.reduce((s, n) => s + noteBeats(n), 0);

      const mInfo = {
        startX:     staveX,
        endX:       staveX + staveWidth,
        noteStartX,
        noteWidth,
        staveY:     topLineY,
        usedBeats,
        isFull:     usedBeats >= bpm - 0.001,
      };

      try {
        const startIdx      = globalNoteIdx;
        const measureAccState = {};  // tracks within-measure accidental state
        const vfNotes  = mNotes.map((n, j) => {
          let s = styleMap ? (styleMap[startIdx + j] || null) : null;
          if (interactive && selectedNoteIdx !== null && startIdx + j === selectedNoteIdx) {
            s = { fillStyle: '#2563eb', strokeStyle: '#2563eb' };
          }
          return buildStaveNote(n, s, measureAccState);
        });

        // ---- Cross-measure tie resolution ----
        // If the previous measure ended with a tieStart note, connect it to
        // the first note of this measure (if it's on the same row).
        if (pendingTie) {
          if (vfNotes.length > 0 && mNotes[0] && mNotes[0].tieEnd && pendingTie.row === row) {
            tiesToDraw.push(new VF.StaveTie({
              first_note:    pendingTie.vfNote,
              last_note:     vfNotes[0],
              first_indices: [0],
              last_indices:  [0],
            }));
          }
          pendingTie = null;  // consumed (or skipped for cross-row)
        }
        // If the last note of this measure starts a tie, remember it.
        if (vfNotes.length > 0 && mNotes[mNotes.length - 1].tieStart) {
          pendingTie = { vfNote: vfNotes[vfNotes.length - 1], row };
        }

        const ghosts       = buildGhostPadding(usedBeats, VF);
        const allTickables = [...vfNotes, ...ghosts];

        if (allTickables.length > 0) {
          // Build beams BEFORE voice.draw() so VexFlow suppresses individual
          // note flags on beamed notes when they are drawn.
          //
          // Pass ALL notes in the measure (including quarters, halves, rests)
          // so VexFlow can track beat positions and respect beat boundaries
          // when grouping beams — e.g. a quarter followed by 4 eighths in 6/8
          // should produce [lone eighth][three-eighth beam], not [three-eighth
          // beam][lone eighth].
          let beams = [];
          const hasBeamable = mNotes.some(n =>
            (n.duration === '8' || n.duration === '16') && !n.duration.endsWith('r')
          );
          if (hasBeamable) {
            beams = buildBeams(mNotes, vfNotes, VF);
          }

          const voice = new VF.Voice(getVoiceDef());
          voice.setMode(VF.Voice.Mode.SOFT);
          voice.addTickables(allTickables);

          // Format then draw — ghost notes fill remaining beats so VexFlow
          // distributes proportional spacing automatically.
          new VF.Formatter()
            .joinVoices([voice])
            .format([voice], Math.max(60, noteEndX - noteStartX - 10));

          voice.draw(ctx, stave);

          // Now draw the beam lines (flags already suppressed above)
          beams.forEach(beam => beam.setContext(ctx).draw());
        }
      } catch (err) {
        console.warn('VexFlow render error, measure', i, ':', err.message);
        pendingTie = null;
      }

      measureInfo.push(mInfo);
      globalNoteIdx += mNotes.length;
    }

    // Draw all cross-measure ties (both notes are already rendered above)
    tiesToDraw.forEach(tie => {
      try { tie.setContext(ctx).draw(); } catch (_) {}
    });

    // Tag rendered note elements for drag support
    if (interactive) {
      const svg = containerEl.querySelector('svg');
      if (svg) {
        svg.querySelectorAll('.vf-stavenote').forEach((g, idx) => {
          g.setAttribute('data-note-idx', idx);
        });
      }
    }
  }

  // =========================================================================
  // Ghost note overlay
  // =========================================================================

  function ensureGhost(svg) {
    if (ghostEl && ghostEl.parentNode === svg) return;
    const ns = 'http://www.w3.org/2000/svg';
    ghostEl = document.createElementNS(ns, 'ellipse');
    ghostEl.classList.add('ghost-note');
    ghostEl.setAttribute('pointer-events', 'none');
    ghostEl.setAttribute('visibility', 'hidden');
    svg.appendChild(ghostEl);
  }

  function updateGhostShape() {
    if (!ghostEl) return;
    const base  = selectedDur.replace('r', '');
    const shape = GHOST_SHAPES[base] || GHOST_SHAPES.q;
    ghostEl.setAttribute('rx', shape.rx);
    ghostEl.setAttribute('ry', shape.ry);
    ghostEl.setAttribute('fill', shape.fill);
    ghostEl.setAttribute('stroke', shape.stroke);
    ghostEl.setAttribute('stroke-width', '1.5');
    ghostEl.setAttribute('opacity', isDotted ? '0.55' : '0.4');
  }

  function showGhost(x, y) {
    if (!ghostEl) return;
    ghostEl.setAttribute('cx', x);
    ghostEl.setAttribute('cy', y);
    ghostEl.setAttribute('visibility', 'visible');
  }

  function hideGhost() {
    if (ghostEl) ghostEl.setAttribute('visibility', 'hidden');
  }

  // =========================================================================
  // Editor actions
  // =========================================================================

  function setDuration(dur) {
    selectedDur = dur;
    document.querySelectorAll('.duration-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.dur === dur);
    });
    updateGhostShape();
  }

  function toggleDot() {
    isDotted = !isDotted;
    document.getElementById('btn-dot')?.classList.toggle('active', isDotted);
    updateGhostShape();
  }

  function setAccidental(acc) {
    selectedAcc = acc;
    document.querySelectorAll('.acc-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.acc === acc);
    });
  }

  function resetAccidental() { setAccidental(''); }

  function updateSelectionToolbar() {
    const controls = document.getElementById('selected-note-controls');
    if (!controls) return;
    controls.style.display = selectedNoteIdx !== null ? 'flex' : 'none';
  }

  function selectNote(idx) {
    selectedNoteIdx = idx;
    updateSelectionToolbar();
    refresh();
  }

  function deselectNote() {
    if (selectedNoteIdx === null) return;
    selectedNoteIdx = null;
    updateSelectionToolbar();
    refresh();
  }

  function applyAccidentalToSelected(type) {
    if (selectedNoteIdx === null) return;
    const note = userNotes[selectedNoteIdx];
    if (!note || note.duration.endsWith('r')) return;

    const slash      = note.key.indexOf('/');
    const letterAcc  = note.key.slice(0, slash);
    const octave     = note.key.slice(slash);
    const letter     = letterAcc.charAt(0);
    const curAcc     = letterAcc.slice(1);
    const keyDefault = getKeySigAccidentals()[letter] || '';

    let newAcc;
    if (type === '') {
      newAcc = keyDefault;
    } else if (type === 'raise') {
      if      (curAcc === '')   newAcc = '#';
      else if (curAcc === 'b')  newAcc = '';
      else if (curAcc === '#')  newAcc = '##';
      else if (curAcc === 'bb') newAcc = 'b';
      else                      newAcc = curAcc;
    } else {
      if      (curAcc === '')   newAcc = 'b';
      else if (curAcc === '#')  newAcc = '';
      else if (curAcc === 'b')  newAcc = 'bb';
      else if (curAcc === '##') newAcc = '#';
      else                      newAcc = curAcc;
    }

    const newKey = letter + newAcc + octave;
    userNotes[selectedNoteIdx].key = newKey;
    const idx = selectedNoteIdx;
    if (userNotes[idx].tieStart && idx + 1 < userNotes.length && userNotes[idx + 1].tieEnd) {
      userNotes[idx + 1].key = newKey;
    } else if (userNotes[idx].tieEnd && idx > 0 && userNotes[idx - 1].tieStart) {
      userNotes[idx - 1].key = newKey;
    }
    refresh();
  }

  /**
   * Return true if a note of `beats` duration fits in the current incomplete measure.
   * Prevents dotted notes from silently overflowing a measure into the next one.
   */
  function fitsInCurrentMeasure(beats) {
    const bpm  = getBeatsPerMeasure();
    const incomplete = measureInfo.find(m => !m.isFull);
    if (!incomplete) return true;   // all full — bTotal check will block anyway
    return beats <= (bpm - incomplete.usedBeats) + 0.001;
  }

  function placeRest() {
    const restDur = selectedDur + 'r';
    const beats   = noteBeats({ duration: restDur, dotted: isDotted });
    const bTotal  = (typeof BEATS_TOTAL !== 'undefined') ? BEATS_TOTAL : Infinity;
    if (currentBeats + beats > bTotal + 0.001 || !fitsInCurrentMeasure(beats)) {
      flashError(); return;
    }
    userNotes.push({ key: getRestKey(), duration: restDur, dotted: isDotted });
    currentBeats += beats;
    refresh();
  }

  // =========================================================================
  // Interaction handlers (exercise page)
  // =========================================================================

  function attachInteractionHandlers(containerEl) {
    const svg = containerEl.querySelector('svg');
    if (!svg) return;

    ensureGhost(svg);
    updateGhostShape();
    svg.style.touchAction = 'none';

    // --- Shared pointer logic ---

    function ghostPos(mx, my) {
      const sy = findStaveY(my);
      if (!sy) return null;
      const mIdx = findMeasure(mx, my);
      if (mIdx < 0 || measureInfo[mIdx].isFull) return null;
      const step = stepFromY(my, sy);
      const tblIdx = step + STEP_OFFSET;
      if (tblIdx < 0 || tblIdx >= getNoteTable().length) return null;
      return { x: propX(measureInfo[mIdx], measureInfo[mIdx].usedBeats), y: snappedY(step, sy) };
    }

    function onPointerStart(mx, my, targetEl) {
      pointerStartPos = { x: mx, y: my };

      const noteG = targetEl ? targetEl.closest('[data-note-idx]') : null;
      if (noteG) {
        const idx = parseInt(noteG.getAttribute('data-note-idx'), 10);
        if (idx >= 0 && idx < userNotes.length && !userNotes[idx].duration.endsWith('r')) {
          const sy = findStaveY(my);
          if (sy) {
            pendingDragTarget = {
              noteIdx:      idx,
              staveY:       sy,
              origSnappedY: snappedY(stepFromY(my, sy), sy),
              gEl:          noteG,
            };
            return;
          }
        }
      }

      pendingDragTarget = null;
      const pos = ghostPos(mx, my);
      if (pos) showGhost(pos.x, pos.y); else hideGhost();
    }

    function onPointerMove(mx, my) {
      if (dragState) {
        const step  = stepFromY(my, dragState.staveY);
        const snY   = snappedY(step, dragState.staveY);
        const delta = snY - dragState.origSnappedY;
        dragState.gEl.setAttribute('transform', `translate(0, ${delta})`);
        hideGhost();
        return;
      }

      if (pendingDragTarget && pointerStartPos) {
        const dx = mx - pointerStartPos.x;
        const dy = my - pointerStartPos.y;
        if (Math.sqrt(dx * dx + dy * dy) > 8) {
          dragState = pendingDragTarget;
          pendingDragTarget = null;
          containerEl.classList.add('dragging');
        }
        return;
      }

      const pos = ghostPos(mx, my);
      if (pos) showGhost(pos.x, pos.y); else hideGhost();
    }

    function onPointerEnd(mx, my) {
      if (dragState) {
        const newKey = stepToNote(stepFromY(my, dragState.staveY));
        if (newKey) {
          const idx = dragState.noteIdx;
          userNotes[idx].key = newKey;
          if (userNotes[idx].tieStart && idx + 1 < userNotes.length && userNotes[idx + 1].tieEnd) {
            userNotes[idx + 1].key = newKey;
          } else if (userNotes[idx].tieEnd && idx > 0 && userNotes[idx - 1].tieStart) {
            userNotes[idx - 1].key = newKey;
          }
        }
        containerEl.classList.remove('dragging');
        dragState = null;
        pendingDragTarget = null;
        pointerStartPos   = null;
        refresh();
        return;
      }

      if (pendingDragTarget) {
        // Tap on existing note — select or deselect
        const idx = pendingDragTarget.noteIdx;
        pendingDragTarget = null;
        pointerStartPos   = null;
        hideGhost();
        if (selectedNoteIdx === idx) {
          deselectNote();
        } else {
          selectNote(idx);
        }
        return;
      }

      pointerStartPos = null;
      hideGhost();

      // Tap on empty area — place new pitched note
      const sy = findStaveY(my);
      if (!sy) return;

      const mIdx = findMeasure(mx, my);
      if (mIdx >= 0 && measureInfo[mIdx].isFull) { flashError(); return; }

      const key = yToNote(my, sy);
      if (!key) return;

      const beats  = noteBeats({ duration: selectedDur, dotted: isDotted });
      const bTotal = (typeof BEATS_TOTAL !== 'undefined') ? BEATS_TOTAL : Infinity;
      if (currentBeats + beats > bTotal + 0.001) { flashError(); return; }

      if (!fitsInCurrentMeasure(beats)) {
        const bpm        = getBeatsPerMeasure();
        const incomplete = measureInfo.find(m => !m.isFull);
        if (!incomplete) { flashError(); return; }
        const remaining  = bpm - incomplete.usedBeats;
        const firstSpec  = beatsToNoteSpec(remaining);
        const secondSpec = beatsToNoteSpec(beats - remaining);
        if (!firstSpec || !secondSpec) { flashError(); return; }
        userNotes.push({ key, duration: firstSpec.duration,  dotted: firstSpec.dotted,  tieStart: true });
        userNotes.push({ key, duration: secondSpec.duration, dotted: secondSpec.dotted, tieEnd:   true });
        currentBeats += beats;
        if (selectedAcc !== '') resetAccidental();
        refresh();
        return;
      }

      userNotes.push({ key, duration: selectedDur, dotted: isDotted });
      currentBeats += beats;
      if (selectedAcc !== '') resetAccidental();
      refresh();
    }

    // --- Mouse events ---
    svg.addEventListener('mousemove', (e) => {
      const rect = svg.getBoundingClientRect();
      onPointerMove(e.clientX - rect.left, e.clientY - rect.top);
    });

    svg.addEventListener('mouseleave', () => {
      if (!dragState) hideGhost();
    });

    svg.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;
      const rect = svg.getBoundingClientRect();
      onPointerStart(e.clientX - rect.left, e.clientY - rect.top, e.target);
      if (pendingDragTarget) e.preventDefault();
    });

    svg.addEventListener('mouseup', (e) => {
      if (e.button !== 0) return;
      const rect = svg.getBoundingClientRect();
      onPointerEnd(e.clientX - rect.left, e.clientY - rect.top);
    });

    // --- Touch events ---
    svg.addEventListener('touchstart', (e) => {
      e.preventDefault();
      const t    = e.touches[0];
      const rect = svg.getBoundingClientRect();
      onPointerStart(
        t.clientX - rect.left,
        t.clientY - rect.top,
        document.elementFromPoint(t.clientX, t.clientY)
      );
    }, { passive: false });

    svg.addEventListener('touchmove', (e) => {
      e.preventDefault();
      const t    = e.touches[0];
      const rect = svg.getBoundingClientRect();
      onPointerMove(t.clientX - rect.left, t.clientY - rect.top);
    }, { passive: false });

    svg.addEventListener('touchend', (e) => {
      e.preventDefault();
      const t    = e.changedTouches[0];
      const rect = svg.getBoundingClientRect();
      onPointerEnd(t.clientX - rect.left, t.clientY - rect.top);
    }, { passive: false });
  }

  // =========================================================================
  // Refresh (exercise page)
  // =========================================================================

  function refresh() {
    if (selectedNoteIdx !== null && selectedNoteIdx >= userNotes.length) {
      selectedNoteIdx = null;
    }
    const el = document.getElementById('notation-container');
    if (!el) return;
    renderStaves(el, userNotes, NUM_MEASURES, true, null);
    attachInteractionHandlers(el);
    updateSelectionToolbar();
  }

  // =========================================================================
  // MIDI input (melodic dictation)
  // =========================================================================

  window.placeMidiNote = function (midiNumber) {
    const key = (typeof midiToVexKey === 'function')
      ? midiToVexKey(midiNumber, (typeof KEY_SIGNATURE !== 'undefined') ? KEY_SIGNATURE : 'C')
      : null;
    if (!key) return;

    const beats  = noteBeats({ duration: selectedDur, dotted: isDotted });
    const bTotal = (typeof BEATS_TOTAL !== 'undefined') ? BEATS_TOTAL : Infinity;
    if (currentBeats + beats > bTotal + 0.001) { flashError(); return; }

    if (!fitsInCurrentMeasure(beats)) {
      const bpm        = getBeatsPerMeasure();
      const incomplete = measureInfo.find(m => !m.isFull);
      if (!incomplete) { flashError(); return; }
      const remaining  = bpm - incomplete.usedBeats;
      const firstSpec  = beatsToNoteSpec(remaining);
      const secondSpec = beatsToNoteSpec(beats - remaining);
      if (!firstSpec || !secondSpec) { flashError(); return; }
      userNotes.push({ key, duration: firstSpec.duration,  dotted: firstSpec.dotted,  tieStart: true });
      userNotes.push({ key, duration: secondSpec.duration, dotted: secondSpec.dotted, tieEnd:   true });
      currentBeats += beats;
      refresh();
      return;
    }

    userNotes.push({ key, duration: selectedDur, dotted: isDotted });
    currentBeats += beats;
    // Intentionally do NOT reset selectedAcc — MIDI input leaves accidental state alone.
    refresh();
  };

  // =========================================================================
  // Public API (results page)
  // =========================================================================

  window.renderReadOnlyStave = function (containerId, notes) {
    const el = document.getElementById(containerId);
    if (!el || !VF) return;
    const bpm = getBeatsPerMeasure();
    const n = notes.length
      ? Math.max(1, Math.ceil(notes.reduce((s, n) => s + noteBeats(n), 0) / bpm))
      : 1;
    renderStaves(el, notes, n, false, null);
  };

  window.renderStyledStave = function (containerId, notes, styleMap) {
    const el = document.getElementById(containerId);
    if (!el || !VF) return;
    const bpm = getBeatsPerMeasure();
    const n = notes.length
      ? Math.max(1, Math.ceil(notes.reduce((s, n) => s + noteBeats(n), 0) / bpm))
      : 1;
    renderStaves(el, notes, n, false, styleMap);
  };

  // =========================================================================
  // DOMContentLoaded
  // =========================================================================
  document.addEventListener('DOMContentLoaded', () => {
    const vfError = initVexFlow();
    if (vfError) {
      console.error('[notation.js]', vfError);
      const c = document.getElementById('notation-container');
      if (c) c.innerHTML =
        `<div class="alert alert-danger m-2"><strong>Notation error:</strong> ${vfError}</div>`;
    }

    // --- Exercise page setup ---
    const container = document.getElementById('notation-container');
    if (container && !vfError) refresh();

    // Duration buttons
    document.querySelectorAll('.duration-btn').forEach((btn) => {
      btn.addEventListener('click', () => setDuration(btn.dataset.dur));
    });

    // Dotted toggle
    document.getElementById('btn-dot')?.addEventListener('click', toggleDot);

    // Place Rest button
    document.getElementById('btn-place-rest')?.addEventListener('click', placeRest);

    // Accidental buttons
    document.querySelectorAll('.acc-btn').forEach((btn) => {
      btn.addEventListener('click', () => setAccidental(btn.dataset.acc));
    });

    // Selected note editing
    document.getElementById('btn-sel-sharp')?.addEventListener('click', () => applyAccidentalToSelected('raise'));
    document.getElementById('btn-sel-flat')?.addEventListener('click', () => applyAccidentalToSelected('lower'));
    document.getElementById('btn-sel-natural')?.addEventListener('click', () => applyAccidentalToSelected(''));
    document.getElementById('btn-sel-deselect')?.addEventListener('click', deselectNote);

    // Undo
    document.getElementById('btn-undo')?.addEventListener('click', () => {
      if (!userNotes.length) return;
      const removed = userNotes.pop();
      currentBeats  = Math.max(0, currentBeats - noteBeats(removed));
      // Tied pairs are placed together — undo removes both notes at once.
      if (removed.tieEnd && userNotes.length && userNotes[userNotes.length - 1].tieStart) {
        const partner = userNotes.pop();
        currentBeats  = Math.max(0, currentBeats - noteBeats(partner));
      }
      refresh();
    });

    // Clear
    document.getElementById('btn-clear')?.addEventListener('click', () => {
      userNotes = []; currentBeats = 0; refresh();
    });

    // Submit
    document.getElementById('btn-submit')?.addEventListener('click', async () => {
      if (!userNotes.length) { alert('Place at least one note before submitting.'); return; }
      const btn = document.getElementById('btn-submit');
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Grading…';
      try {
        const res  = await fetch(`/submit/${MELODY_ID}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ notes: userNotes }),
        });
        const data = await res.json();
        if (data.redirect) { window.location.href = data.redirect; return; }
        alert(data.error || 'Submission failed.');
      } catch (err) {
        console.error(err); alert('Network error.');
      }
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-check2-circle me-1"></i>Submit';
    });

    // --- Keyboard shortcuts ---
    document.addEventListener('keydown', (e) => {
      // Don't fire inside text inputs
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' ||
          e.target.isContentEditable) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (!document.getElementById('notation-container')) return;  // exercise page only

      switch (e.key) {
        case '3': setDuration('16');       e.preventDefault(); break;
        case '4': setDuration('8');        e.preventDefault(); break;
        case '5': setDuration('q');        e.preventDefault(); break;
        case '6': setDuration('h');        e.preventDefault(); break;
        case '7': setDuration('w');        e.preventDefault(); break;
        case '.': toggleDot();             e.preventDefault(); break;
        case ',': placeRest();             e.preventDefault(); break;
        case '0': setAccidental('');       e.preventDefault(); break;
        case '-': setAccidental('lower');  e.preventDefault(); break;
        case '=': setAccidental('raise');  e.preventDefault(); break;
      }
    });

    // --- Results page ---
    if (typeof CORRECT_NOTES !== 'undefined' && typeof USER_NOTES !== 'undefined') {
      window.renderReadOnlyStave('correct-staff', CORRECT_NOTES);

      // Pitch comparison: convert to MIDI number so enharmonic equivalents
      // (G# / Ab, C# / Db, etc.) are treated as correct.
      const _PC = {
        c:0,'c#':1,db:1,d:2,'d#':3,eb:3,e:4,
        f:5,'f#':6,gb:6,g:7,'g#':8,ab:8,
        a:9,'a#':10,bb:10,b:11,
      };
      function keyToMidi(key) {
        const slash = key.indexOf('/');
        if (slash < 0) return null;
        const la  = key.slice(0, slash).trim().toLowerCase();
        const oct = parseInt(key.slice(slash + 1), 10);
        const pc  = _PC[la];
        return (pc != null && !isNaN(oct)) ? (oct + 1) * 12 + pc : null;
      }
      function pitchesMatch(k1, k2) {
        if (k1.toLowerCase() === k2.toLowerCase()) return true;
        const m1 = keyToMidi(k1), m2 = keyToMidi(k2);
        return m1 !== null && m2 !== null && m1 === m2;
      }

      const styleMap = USER_NOTES.map((un, i) => {
        if (i >= CORRECT_NOTES.length) return { fillStyle: 'red', strokeStyle: 'red' };
        const cn      = CORRECT_NOTES[i];
        const pitchOk = pitchesMatch(un.key, cn.key);
        const durOk   = un.duration === cn.duration;
        return (pitchOk && durOk) ? null : { fillStyle: 'red', strokeStyle: 'red' };
      });
      window.renderStyledStave('user-staff', USER_NOTES, styleMap);
    }
  });
})();
