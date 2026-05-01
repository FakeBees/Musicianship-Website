/**
 * holistic.js — Coordinates WAV playback, VexFlow stave notation, and
 * chord block entry for the Holistic Dictation exercise page.
 *
 * Depends on (must be loaded before this file):
 *   - chord_block_utils.js  (window.ChordBlockUtils)
 *   - notation.js           (window.renderReadOnlyStave, window.renderStyledStave)
 *   - player.js             (window.playNoteArray, window.playChordArray)
 *   - VexFlow               (Vex.Flow)
 *   - Tone.js
 *
 * Template variables expected:
 *   EXERCISE_ID, WAV_URL, KEY_SIGNATURE, TIME_SIG_TOP, TIME_SIG_BOTTOM,
 *   NUM_MEASURES, MELODY_CLEF, EXTRA_LINES,
 *   UNLOCK_SEVENTH, UNLOCK_EXTENSIONS, UNLOCK_SUS
 */

'use strict';

// ---------------------------------------------------------------------------
// Shortcuts into ChordBlockUtils
// ---------------------------------------------------------------------------
const {
  SHARP_NAMES, FLAT_NAMES, FLAT_KEYS, noteNameForPc,
  DIATONIC_SCALES, DIATONIC_QUALITIES_MAJOR, DIATONIC_QUALITIES_MINOR,
  QUALITY_INTERVALS, HARM_KEY_REFERENCE,
  formatChordName, computeChordTones,
} = window.ChordBlockUtils;

// ---------------------------------------------------------------------------
// Per-stave note state
// Store notes per line key. Melody lines use VexFlow input like notation.js.
// ---------------------------------------------------------------------------

const lineNotes = {};  // lineKey -> [{key, duration, dotted?}, ...]

function getNotesForLine(lineKey) {
  return lineNotes[lineKey] || [];
}

// ---------------------------------------------------------------------------
// WAV Playback
// ---------------------------------------------------------------------------

let wavPlayCount = 0;

function initWavPlayback() {
  const audio  = document.getElementById('wav-player');
  const btnPlay = document.getElementById('btn-wav-play');
  const btnStop = document.getElementById('btn-wav-stop');
  const counter = document.getElementById('wav-play-count');

  if (!audio) return;

  // Detect 404 / load error
  audio.addEventListener('error', () => {
    if (btnPlay) {
      btnPlay.disabled = true;
      btnPlay.textContent = 'Audio not available';
      btnPlay.classList.remove('btn-success');
      btnPlay.classList.add('btn-secondary');
    }
  });

  if (btnPlay) {
    btnPlay.addEventListener('click', async () => {
      const scaleChecked   = document.getElementById('cb-scale-ref')?.checked;
      const harmonyChecked = document.getElementById('cb-harmony-ref')?.checked;
      const beatChecked    = document.getElementById('cb-beat-ref')?.checked;

      // Build a sequential chain of reference steps before the WAV plays
      const steps = [];
      if (scaleChecked)   steps.push('scale');
      if (harmonyChecked) steps.push('harmony');
      if (beatChecked)    steps.push('beat');
      steps.push('wav');

      btnPlay.disabled = true;
      btnPlay.innerHTML = '<i class="bi bi-volume-up me-1"></i>Playing…';

      let stepIdx = 0;
      function runNext() {
        if (stepIdx >= steps.length) return;
        const step = steps[stepIdx++];

        if (step === 'scale') {
          const scaleData  = (typeof HOLISTIC_KEY_SCALES !== 'undefined' ? HOLISTIC_KEY_SCALES : {})[KEY_SIGNATURE]
                          || ['c/4','d/4','e/4','f/4','g/4','a/4','b/4','c/5'];
          const scaleNotes = scaleData.map(k => ({ key: k, duration: 'q' }));
          const triadNotes = [0, 2, 4, 7].map(j => ({ key: scaleData[j], duration: 'q' }));
          const refNotes   = [...scaleNotes, { key: 'b/4', duration: 'qr' }, ...triadNotes];
          window.playNoteArray(refNotes, 144, runNext);

        } else if (step === 'harmony') {
          const chords = HARM_KEY_REFERENCE[KEY_SIGNATURE]
            || (KEY_SIGNATURE.endsWith('m')
                ? HARM_KEY_REFERENCE['Am']
                : HARM_KEY_REFERENCE['C']);
          window.playChordArray(chords, 72, runNext);

        } else if (step === 'beat') {
          const tempo  = (typeof EXERCISE_TEMPO !== 'undefined') ? EXERCISE_TEMPO : 100;
          const sigTop = (typeof TIME_SIG_TOP    !== 'undefined') ? TIME_SIG_TOP    : 4;
          const sigBot = (typeof TIME_SIG_BOTTOM !== 'undefined') ? TIME_SIG_BOTTOM : 4;
          window.playCountIn(tempo, sigTop, sigBot, runNext);

        } else if (step === 'wav') {
          // Restore button state, then play the WAV recording
          btnPlay.disabled = false;
          btnPlay.innerHTML = '<i class="bi bi-play-fill"></i> Play Recording';
          audio.currentTime = 0;
          audio.play().then(() => {
            wavPlayCount++;
            if (counter) counter.textContent = 'Plays: ' + wavPlayCount;
            if (btnPlay) btnPlay.disabled = true;
            if (btnStop) btnStop.disabled = false;
          }).catch(() => {
            if (btnPlay) {
              btnPlay.disabled = true;
              btnPlay.textContent = 'Audio not available';
            }
          });
        }
      }
      runNext();
    });
  }

  if (btnStop) {
    btnStop.addEventListener('click', () => {
      audio.pause();
      audio.currentTime = 0;
      if (btnPlay) btnPlay.disabled = false;
      if (btnStop) btnStop.disabled = true;
    });
  }

  audio.addEventListener('ended', () => {
    if (btnPlay) btnPlay.disabled = false;
    if (btnStop) btnStop.disabled = true;
  });
}

// ---------------------------------------------------------------------------
// VexFlow stave rendering for holistic page
// Each stave is a simple interactive notation area (same approach as notation.js
// but here we manage one stave per line key).
// ---------------------------------------------------------------------------

const VF_MEASURES_PER_ROW = 4;
const VF_ROW_HEIGHT  = 120;
const VF_ROW_OFFSET  = 50;
const VF_STAVE_X_PAD = 15;
const VF_HALF_SPACE  = 5;
const VF_STEP_OFFSET = 4;
const VF_PROP_PAD    = 12;

const NOTE_TABLES = {
  treble: [
    'c/6','b/5','a/5','g/5','f/5','e/5','d/5','c/5','b/4',
    'a/4','g/4','f/4','e/4','d/4','c/4','b/3','a/3',
  ],
  bass: [
    'e/4','d/4','c/4','b/3','a/3','g/3','f/3','e/3','d/3',
    'c/3','b/2','a/2','g/2','f/2','e/2','d/2','c/2',
  ],
  tenor: [
    'b/4','a/4','g/4','f/4','e/4','d/4','c/4','b/3','a/3',
    'g/3','f/3','e/3','d/3','c/3','b/2','a/2','g/2',
  ],
};

const DURATION_BEATS = {
  w:4, h:2, q:1, '8':0.5, '16':0.25,
  wr:4, hr:2, qr:1, '8r':0.5, '16r':0.25,
};

const KEY_SIG_ACCIDENTALS = {
  'C':{}, 'G':{f:'#'}, 'D':{f:'#',c:'#'}, 'A':{f:'#',c:'#',g:'#'},
  'E':{f:'#',c:'#',g:'#',d:'#'}, 'B':{f:'#',c:'#',g:'#',d:'#',a:'#'},
  'F#':{f:'#',c:'#',g:'#',d:'#',a:'#',e:'#'},
  'F':{b:'b'}, 'Bb':{b:'b',e:'b'}, 'Eb':{b:'b',e:'b',a:'b'},
  'Ab':{b:'b',e:'b',a:'b',d:'b'}, 'Db':{b:'b',e:'b',a:'b',d:'b',g:'b'},
  'Gb':{b:'b',e:'b',a:'b',d:'b',g:'b',c:'b'},
  'Am':{}, 'Em':{f:'#'}, 'Bm':{f:'#',c:'#'}, 'Dm':{b:'b'},
  'Gm':{b:'b',e:'b'}, 'Cm':{b:'b',e:'b',a:'b'}, 'Fm':{b:'b',e:'b',a:'b',d:'b'},
};

function keySigAcc() { return KEY_SIG_ACCIDENTALS[KEY_SIGNATURE] || {}; }

function getDiatonicPitch(baseNote, acc) {
  const sl = baseNote.indexOf('/');
  const letter = baseNote.slice(0, sl);
  const octave = baseNote.slice(sl);
  const a = (acc || {})[letter] || '';
  return letter + a + octave;
}

function noteBeats(n) {
  const base = DURATION_BEATS[n.duration] || 1;
  return n.dotted ? base * 1.5 : base;
}

function beatsPerMeasure() {
  return TIME_SIG_TOP * (4 / TIME_SIG_BOTTOM);
}

function getRestKey(clef) {
  switch (clef) {
    case 'bass':  return 'd/3';
    case 'tenor': return 'a/3';
    default:      return 'b/4';
  }
}

// ---------------------------------------------------------------------------
// Per-stave editor state (keyed by lineKey)
// ---------------------------------------------------------------------------

const staveEditors = {};  // lineKey -> { notes, selectedDur, isDotted, measureInfo, ... }

// Tracks which stave the mouse is currently over for MIDI routing.
let hoveredMidiTarget = null;

// Globally selected note across all staves (only one note selected at a time).
let selectedNote = { lineKey: null, idx: null };

function getEditor(lineKey) {
  if (!staveEditors[lineKey]) {
    staveEditors[lineKey] = {
      notes:            [],
      selectedDur:      'q',
      isDotted:         false,
      currentBeats:     0,
      measureInfo:      [],
      staveTopYs:       [],
      ghostEl:          null,
      dragState:        null,
      pointerStartPos:  null,
      pendingDragTarget: null,
    };
    lineNotes[lineKey] = staveEditors[lineKey].notes;
  }
  return staveEditors[lineKey];
}

function updateStaveSelectionToolbar(lineKey) {
  const isSelected = selectedNote.lineKey === lineKey && selectedNote.idx !== null;
  const controls = document.querySelector(`[data-line-key="${lineKey}"] .holistic-sel-controls`);
  if (!controls) return;
  controls.style.display = isSelected ? 'flex' : 'none';
}

function selectStaveNote(lineKey, idx, clef, containerEl) {
  selectedNote = { lineKey, idx };
  updateStaveSelectionToolbar(lineKey);
  refreshStave(lineKey, clef, containerEl);
}

function deselectStaveNote(lineKey, clef, containerEl) {
  if (selectedNote.lineKey !== lineKey) return;
  selectedNote = { lineKey: null, idx: null };
  updateStaveSelectionToolbar(lineKey);
  refreshStave(lineKey, clef, containerEl);
}

function applyAccidentalToStave(lineKey, type) {
  if (selectedNote.lineKey !== lineKey || selectedNote.idx === null) return;
  const ed   = getEditor(lineKey);
  const note = ed.notes[selectedNote.idx];
  if (!note || note.duration.endsWith('r')) return;

  const slash      = note.key.indexOf('/');
  const letterAcc  = note.key.slice(0, slash);
  const octave     = note.key.slice(slash);
  const letter     = letterAcc.charAt(0);
  const curAcc     = letterAcc.slice(1);
  const keyDefault = keySigAcc()[letter] || '';

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

  note.key = letter + newAcc + octave;
  const containerEl = document.querySelector(`[data-stave-line-key="${lineKey}"]`);
  const clef = containerEl ? (containerEl.dataset.clef || 'treble') : 'treble';
  refreshStave(lineKey, clef, containerEl);
}

// ---------------------------------------------------------------------------
// VexFlow rendering per stave container
// ---------------------------------------------------------------------------

function renderStaveForLine(lineKey, clef, containerEl) {
  if (typeof Vex === 'undefined') return;
  const VF = Vex.Flow;
  const ed = getEditor(lineKey);
  const notes = ed.notes;

  containerEl.innerHTML = '';
  ed.staveTopYs = [];
  ed.measureInfo = [];

  const totalWidth = containerEl.clientWidth || 800;
  const numMeasures = NUM_MEASURES;
  const numRows  = Math.ceil(numMeasures / VF_MEASURES_PER_ROW);
  const colCount = Math.min(numMeasures, VF_MEASURES_PER_ROW);
  const staveWidth = Math.max(120, Math.floor((totalWidth - VF_STAVE_X_PAD * 2) / colCount));
  const svgHeight  = VF_ROW_OFFSET + numRows * VF_ROW_HEIGHT;
  const bpm = beatsPerMeasure();

  const renderer = new VF.Renderer(containerEl, VF.Renderer.Backends.SVG);
  renderer.resize(totalWidth, svgHeight);
  const ctx = renderer.getContext();

  const keySig = KEY_SIGNATURE;

  // Split notes into measures
  const measureGroups = [];
  let cur = [], beats = 0;
  for (const n of notes) {
    const b = noteBeats(n);
    if (beats + b > bpm + 0.001 && cur.length) {
      measureGroups.push(cur); cur = []; beats = 0;
    }
    cur.push(n); beats += b;
  }
  if (cur.length) measureGroups.push(cur);
  while (measureGroups.length < numMeasures) measureGroups.push([]);

  function getDisplayAcc(noteKey) {
    const sl = noteKey.indexOf('/');
    const la = noteKey.slice(0, sl);
    const letter = la.charAt(0);
    const noteAcc = la.slice(1);
    const keyDefault = keySigAcc()[letter] || '';
    if (noteAcc === keyDefault) return null;
    if (noteAcc === '') return 'n';
    return noteAcc;
  }

  let globalNoteIdx = 0;

  for (let i = 0; i < numMeasures; i++) {
    const row    = Math.floor(i / VF_MEASURES_PER_ROW);
    const col    = i % VF_MEASURES_PER_ROW;
    const staveY = VF_ROW_OFFSET + row * VF_ROW_HEIGHT;
    const staveX = VF_STAVE_X_PAD + col * staveWidth;

    const stave = new VF.Stave(staveX, staveY, staveWidth);
    if (col === 0) stave.addClef(clef);
    if (i === 0) {
      if (keySig !== 'C') stave.addKeySignature(keySig);
      stave.addTimeSignature(TIME_SIG_TOP + '/' + TIME_SIG_BOTTOM);
    }
    stave.setContext(ctx).draw();

    const topLineY   = stave.getYForLine(0);
    const noteStartX = stave.getNoteStartX();
    const noteEndX   = stave.getNoteEndX();
    const noteWidth  = Math.max(60, noteEndX - noteStartX - VF_PROP_PAD * 2);

    ed.staveTopYs.push(topLineY);

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
    ed.measureInfo.push(mInfo);

    const startIdx = globalNoteIdx;

    try {
      const vfNotes = mNotes.map((n, j) => {
        const isRest = n.duration.endsWith('r');
        const vfDur = (n.dotted && !isRest) ? n.duration + 'd' : n.duration;
        const sn = new VF.StaveNote({ keys: [n.key], duration: vfDur, clef });
        if (n.dotted) sn.addModifier(new VF.Dot(), 0);
        if (!isRest) {
          const da = getDisplayAcc(n.key);
          if (da) sn.addModifier(new VF.Accidental(da), 0);
        }
        if (selectedNote.lineKey === lineKey && selectedNote.idx === startIdx + j) {
          sn.setStyle({ fillStyle: '#2563eb', strokeStyle: '#2563eb' });
        }
        return sn;
      });

      // Ghost padding
      let left = bpm - usedBeats;
      const ghosts = [];
      const durMap = [{beats:4,dur:'w'},{beats:2,dur:'h'},{beats:1,dur:'q'},{beats:0.5,dur:'8'},{beats:0.25,dur:'16'}];
      for (const {beats: b, dur} of durMap) {
        while (left >= b - 0.001) {
          ghosts.push(new VF.GhostNote({ duration: dur }));
          left -= b;
        }
      }

      const all = [...vfNotes, ...ghosts];
      if (all.length > 0) {
        const voice = new VF.Voice({ num_beats: TIME_SIG_TOP, beat_value: TIME_SIG_BOTTOM });
        voice.setMode(VF.Voice.Mode.SOFT);
        voice.addTickables(all);
        new VF.Formatter().joinVoices([voice]).format([voice], Math.max(60, noteEndX - noteStartX - 10));
        voice.draw(ctx, stave);
      }
    } catch (e) {
      console.warn('VexFlow render error measure', i, ':', e.message);
    }

    globalNoteIdx += mNotes.length;
  }

  // Tag notes for drag
  const svg = containerEl.querySelector('svg');
  if (svg) {
    svg.querySelectorAll('.vf-stavenote').forEach((g, idx) => {
      g.setAttribute('data-note-idx', idx);
    });
    attachStaveInteraction(lineKey, clef, containerEl, svg);
  }
}

function attachStaveInteraction(lineKey, clef, containerEl, svg) {
  const ed  = getEditor(lineKey);
  const tbl = NOTE_TABLES[clef] || NOTE_TABLES.treble;

  // Remove old listeners by cloning the SVG node
  const newSvg = svg.cloneNode(true);
  svg.parentNode.replaceChild(newSvg, svg);
  const s = newSvg;
  s.style.touchAction = 'none';

  // Ghost ellipse
  {
    const ns = 'http://www.w3.org/2000/svg';
    ed.ghostEl = document.createElementNS(ns, 'ellipse');
    ed.ghostEl.setAttribute('pointer-events', 'none');
    ed.ghostEl.setAttribute('visibility', 'hidden');
    ed.ghostEl.setAttribute('rx', '6');
    ed.ghostEl.setAttribute('ry', '4');
    ed.ghostEl.setAttribute('fill', '#555');
    ed.ghostEl.setAttribute('stroke', '#555');
    ed.ghostEl.setAttribute('stroke-width', '1.5');
    ed.ghostEl.setAttribute('opacity', '0.4');
    s.appendChild(ed.ghostEl);
  }

  // Re-tag notes for selection
  s.querySelectorAll('.vf-stavenote').forEach((g, idx) => {
    g.setAttribute('data-note-idx', idx);
  });

  function findStaveY(cy) {
    for (const sy of ed.staveTopYs) {
      if (cy >= sy - 20 && cy <= sy + 60) return sy;
    }
    return null;
  }

  function findMeasureIdx(mx, cy) {
    const sy = findStaveY(cy);
    if (sy === null) return -1;
    for (let i = 0; i < ed.measureInfo.length; i++) {
      const m = ed.measureInfo[i];
      if (mx >= m.startX && mx <= m.endX && m.staveY === sy) return i;
    }
    return -1;
  }

  function sfY(cy, sy) { return Math.round((cy - sy) / VF_HALF_SPACE); }
  function snY(step, sy) { return sy + step * VF_HALF_SPACE; }

  function stepToNote(step) {
    const idx = step + VF_STEP_OFFSET;
    if (idx < 0 || idx >= tbl.length) return null;
    return getDiatonicPitch(tbl[idx], keySigAcc());
  }

  function ghostPos(mx, my) {
    const sy = findStaveY(my);
    if (!sy) return null;
    const mIdx = findMeasureIdx(mx, my);
    if (mIdx < 0 || ed.measureInfo[mIdx].isFull) return null;
    const step = sfY(my, sy);
    const tblIdx = step + VF_STEP_OFFSET;
    if (tblIdx < 0 || tblIdx >= tbl.length) return null;
    const mInfo = ed.measureInfo[mIdx];
    return {
      x: mInfo.noteStartX + VF_PROP_PAD + (mInfo.usedBeats / beatsPerMeasure()) * mInfo.noteWidth,
      y: snY(step, sy),
    };
  }

  function showGhostAt(mx, my) {
    const pos = ghostPos(mx, my);
    if (pos && ed.ghostEl) {
      ed.ghostEl.setAttribute('cx', pos.x);
      ed.ghostEl.setAttribute('cy', pos.y);
      ed.ghostEl.setAttribute('visibility', 'visible');
    } else if (ed.ghostEl) {
      ed.ghostEl.setAttribute('visibility', 'hidden');
    }
  }

  function hideGhostEl() {
    if (ed.ghostEl) ed.ghostEl.setAttribute('visibility', 'hidden');
  }

  function onPointerStart(mx, my, targetEl) {
    ed.pointerStartPos = { x: mx, y: my };

    const noteG = targetEl ? targetEl.closest('[data-note-idx]') : null;
    if (noteG) {
      const nIdx = parseInt(noteG.getAttribute('data-note-idx'), 10);
      if (nIdx >= 0 && nIdx < ed.notes.length && !ed.notes[nIdx].duration.endsWith('r')) {
        const sy = findStaveY(my);
        if (sy) {
          ed.pendingDragTarget = {
            noteIdx:      nIdx,
            staveY:       sy,
            origSnappedY: snY(sfY(my, sy), sy),
            gEl:          noteG,
          };
          return;
        }
      }
    }

    ed.pendingDragTarget = null;
    showGhostAt(mx, my);
  }

  function onPointerMove(mx, my) {
    hoveredMidiTarget = { lineKey, clef, containerEl };

    if (ed.dragState) {
      const step  = sfY(my, ed.dragState.staveY);
      const delta = snY(step, ed.dragState.staveY) - ed.dragState.origSnappedY;
      ed.dragState.gEl.setAttribute('transform', `translate(0, ${delta})`);
      hideGhostEl();
      return;
    }

    if (ed.pendingDragTarget && ed.pointerStartPos) {
      const dx = mx - ed.pointerStartPos.x;
      const dy = my - ed.pointerStartPos.y;
      if (Math.sqrt(dx * dx + dy * dy) > 8) {
        ed.dragState = ed.pendingDragTarget;
        ed.pendingDragTarget = null;
        containerEl.classList.add('dragging');
      }
      return;
    }

    showGhostAt(mx, my);
  }

  function onPointerEnd(mx, my) {
    if (ed.dragState) {
      const newKey = stepToNote(sfY(my, ed.dragState.staveY));
      if (newKey) ed.notes[ed.dragState.noteIdx].key = newKey;
      containerEl.classList.remove('dragging');
      ed.dragState = null;
      ed.pendingDragTarget = null;
      ed.pointerStartPos   = null;
      refreshStave(lineKey, clef, containerEl);
      return;
    }

    if (ed.pendingDragTarget) {
      const nIdx = ed.pendingDragTarget.noteIdx;
      ed.pendingDragTarget = null;
      ed.pointerStartPos   = null;
      hideGhostEl();
      if (selectedNote.lineKey === lineKey && selectedNote.idx === nIdx) {
        deselectStaveNote(lineKey, clef, containerEl);
      } else {
        selectStaveNote(lineKey, nIdx, clef, containerEl);
      }
      return;
    }

    ed.pointerStartPos = null;
    hideGhostEl();

    const sy = findStaveY(my);
    if (!sy) return;
    const mIdx = findMeasureIdx(mx, my);
    if (mIdx >= 0 && ed.measureInfo[mIdx].isFull) { flashStave(s); return; }

    const key = stepToNote(sfY(my, sy));
    if (!key) return;

    const beats  = noteBeats({ duration: ed.selectedDur, dotted: ed.isDotted });
    const bTotal = NUM_MEASURES * beatsPerMeasure();
    if (ed.currentBeats + beats > bTotal + 0.001) { flashStave(s); return; }

    const bpm        = beatsPerMeasure();
    const incomplete = ed.measureInfo.find(m => !m.isFull);
    if (incomplete && beats > bpm - incomplete.usedBeats + 0.001) { flashStave(s); return; }

    ed.notes.push({ key, duration: ed.selectedDur, dotted: ed.isDotted });
    ed.currentBeats += beats;
    refreshStave(lineKey, clef, containerEl);
  }

  // --- Mouse events ---
  s.addEventListener('mousemove', (e) => {
    const rect = s.getBoundingClientRect();
    onPointerMove(e.clientX - rect.left, e.clientY - rect.top);
  });

  s.addEventListener('mouseleave', () => {
    hideGhostEl();
    if (hoveredMidiTarget && hoveredMidiTarget.lineKey === lineKey) hoveredMidiTarget = null;
  });

  s.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return;
    const rect = s.getBoundingClientRect();
    onPointerStart(e.clientX - rect.left, e.clientY - rect.top, e.target);
    if (ed.pendingDragTarget) e.preventDefault();
  });

  s.addEventListener('mouseup', (e) => {
    if (e.button !== 0) return;
    const rect = s.getBoundingClientRect();
    onPointerEnd(e.clientX - rect.left, e.clientY - rect.top);
  });

  // --- Touch events ---
  s.addEventListener('touchstart', (e) => {
    e.preventDefault();
    const t = e.touches[0];
    const rect = s.getBoundingClientRect();
    onPointerStart(
      t.clientX - rect.left, t.clientY - rect.top,
      document.elementFromPoint(t.clientX, t.clientY)
    );
  }, { passive: false });

  s.addEventListener('touchmove', (e) => {
    e.preventDefault();
    const t = e.touches[0];
    const rect = s.getBoundingClientRect();
    onPointerMove(t.clientX - rect.left, t.clientY - rect.top);
  }, { passive: false });

  s.addEventListener('touchend', (e) => {
    e.preventDefault();
    const t = e.changedTouches[0];
    const rect = s.getBoundingClientRect();
    onPointerEnd(t.clientX - rect.left, t.clientY - rect.top);
  }, { passive: false });
}

function flashStave(svg) {
  svg.style.outline = '2px solid #dc3545';
  setTimeout(() => { svg.style.outline = ''; }, 500);
}

function refreshStave(lineKey, clef, containerEl) {
  renderStaveForLine(lineKey, clef, containerEl);
}

function placeMidiNoteOnStave(lineKey, clef, containerEl, midiNumber) {
  const ed  = getEditor(lineKey);
  const s   = containerEl.querySelector('svg');
  const key = (typeof midiToVexKey === 'function')
    ? midiToVexKey(midiNumber, KEY_SIGNATURE)
    : null;
  if (!key) return;

  const beats = noteBeats({ duration: ed.selectedDur, dotted: ed.isDotted });
  const bTotal = NUM_MEASURES * beatsPerMeasure();
  if (ed.currentBeats + beats > bTotal + 0.001) { if (s) flashStave(s); return; }

  const bpm = beatsPerMeasure();
  const incomplete = ed.measureInfo.find(m => !m.isFull);
  if (incomplete && beats > bpm - incomplete.usedBeats + 0.001) { if (s) flashStave(s); return; }

  ed.notes.push({ key, duration: ed.selectedDur, dotted: ed.isDotted });
  ed.currentBeats += beats;
  refreshStave(lineKey, clef, containerEl);
}

// ---------------------------------------------------------------------------
// Duration / dot controls per stave
// The toolbar below each stave has data-line-key attributes.
// ---------------------------------------------------------------------------

function bindStaveControls(lineKey, clef, containerEl) {
  const ed = getEditor(lineKey);

  // Duration buttons scoped to this line
  document.querySelectorAll('[data-line-key="' + lineKey + '"] .holistic-dur-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      ed.selectedDur = btn.dataset.dur;
      document.querySelectorAll('[data-line-key="' + lineKey + '"] .holistic-dur-btn').forEach(b => {
        b.classList.toggle('active', b === btn);
      });
    });
  });

  // Dot
  const dotBtn = document.querySelector('[data-line-key="' + lineKey + '"] .holistic-dot-btn');
  if (dotBtn) {
    dotBtn.addEventListener('click', () => {
      ed.isDotted = !ed.isDotted;
      dotBtn.classList.toggle('active', ed.isDotted);
    });
  }

  // Rest
  const restBtn = document.querySelector('[data-line-key="' + lineKey + '"] .holistic-rest-btn');
  if (restBtn) {
    restBtn.addEventListener('click', () => {
      const restDur = ed.selectedDur + 'r';
      const beats   = noteBeats({ duration: restDur, dotted: ed.isDotted });
      const bTotal  = NUM_MEASURES * beatsPerMeasure();
      if (ed.currentBeats + beats > bTotal + 0.001) return;
      ed.notes.push({ key: getRestKey(clef), duration: restDur, dotted: ed.isDotted });
      ed.currentBeats += beats;
      refreshStave(lineKey, clef, containerEl);
    });
  }

  // Undo
  const undoBtn = document.querySelector('[data-line-key="' + lineKey + '"] .holistic-undo-btn');
  if (undoBtn) {
    undoBtn.addEventListener('click', () => {
      if (!ed.notes.length) return;
      const removed = ed.notes.pop();
      ed.currentBeats = Math.max(0, ed.currentBeats - noteBeats(removed));
      if (selectedNote.lineKey === lineKey && selectedNote.idx >= ed.notes.length) {
        selectedNote = { lineKey: null, idx: null };
        updateStaveSelectionToolbar(lineKey);
      }
      refreshStave(lineKey, clef, containerEl);
    });
  }

  // Clear
  const clearBtn = document.querySelector('[data-line-key="' + lineKey + '"] .holistic-clear-btn');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      ed.notes.length = 0;
      ed.currentBeats = 0;
      if (selectedNote.lineKey === lineKey) selectedNote = { lineKey: null, idx: null };
      updateStaveSelectionToolbar(lineKey);
      refreshStave(lineKey, clef, containerEl);
    });
  }

  // Selected note editing
  const selSharp   = document.querySelector('[data-line-key="' + lineKey + '"] .holistic-sel-sharp');
  const selFlat    = document.querySelector('[data-line-key="' + lineKey + '"] .holistic-sel-flat');
  const selNatural = document.querySelector('[data-line-key="' + lineKey + '"] .holistic-sel-natural');
  const selDesel   = document.querySelector('[data-line-key="' + lineKey + '"] .holistic-sel-deselect');
  if (selSharp)   selSharp.addEventListener('click',   () => applyAccidentalToStave(lineKey, 'raise'));
  if (selFlat)    selFlat.addEventListener('click',    () => applyAccidentalToStave(lineKey, 'lower'));
  if (selNatural) selNatural.addEventListener('click', () => applyAccidentalToStave(lineKey, ''));
  if (selDesel)   selDesel.addEventListener('click',   () => deselectStaveNote(lineKey, clef, containerEl));
}

// ---------------------------------------------------------------------------
// Chord block row (harmony)
// ---------------------------------------------------------------------------

let harmonyBlocks  = [];
let harmSelectedIdx = null;
let harmNotationMode = 'roman';
let harmSelectedDur  = 'h';   // default: half-note chord blocks

function initHarmonyPanel() {
  buildHarmonyPalette();
  renderHarmonyArea();
  renderHarmonyModifier();

  // Notation toggles
  document.querySelectorAll('.holistic-notation-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      harmNotationMode = btn.dataset.mode;
      document.querySelectorAll('.holistic-notation-btn').forEach(b =>
        b.classList.toggle('active', b === btn));
      buildHarmonyPalette();
      renderHarmonyArea();
    });
  });

  // Duration selector for harmony blocks
  document.querySelectorAll('.holistic-harm-dur-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      harmSelectedDur = btn.dataset.dur;
      document.querySelectorAll('.holistic-harm-dur-btn').forEach(b =>
        b.classList.toggle('active', b === btn));
    });
  });

  // Undo / Clear
  document.getElementById('btn-harm-undo')?.addEventListener('click', () => {
    if (harmonyBlocks.length) {
      harmonyBlocks.pop();
      if (harmSelectedIdx !== null && harmSelectedIdx >= harmonyBlocks.length) {
        harmSelectedIdx = harmonyBlocks.length > 0 ? harmonyBlocks.length - 1 : null;
      }
      renderHarmonyArea();
      renderHarmonyModifier();
    }
  });
  document.getElementById('btn-harm-clear')?.addEventListener('click', () => {
    harmonyBlocks = [];
    harmSelectedIdx = null;
    renderHarmonyArea();
    renderHarmonyModifier();
  });
}

function buildHarmonyPalette() {
  const container = document.getElementById('holistic-diatonic-palette');
  if (!container) return;
  container.innerHTML = '';

  const scale = DIATONIC_SCALES[KEY_SIGNATURE] || DIATONIC_SCALES['C'];
  const isMinor = KEY_SIGNATURE.endsWith('m');
  const qualities = isMinor ? DIATONIC_QUALITIES_MINOR : DIATONIC_QUALITIES_MAJOR;

  scale.forEach((pc, idx) => {
    const quality = qualities[idx];
    const chord = makeHarmChord(pc, quality);
    const label = formatChordName(chord, harmNotationMode, KEY_SIGNATURE);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-outline-secondary palette-btn btn-sm';
    btn.textContent = label;
    btn.addEventListener('click', () => addHarmBlock(makeHarmChord(pc, quality)));
    container.appendChild(btn);
  });
}

function makeHarmChord(rootPc, quality) {
  return {
    root_pc:     rootPc,
    root_name:   noteNameForPc(rootPc, KEY_SIGNATURE),
    quality:     quality,
    bass_pc:     rootPc,
    bass_name:   noteNameForPc(rootPc, KEY_SIGNATURE),
    seventh:     null,
    extensions:  [],
    sus:         null,
    prefer_sharp: null,
    duration:    harmSelectedDur,
  };
}

function addHarmBlock(chord) {
  chord.duration = harmSelectedDur;
  harmonyBlocks.push(chord);
  harmSelectedIdx = harmonyBlocks.length - 1;
  renderHarmonyArea();
  renderHarmonyModifier();
}

function renderHarmonyArea() {
  const area = document.getElementById('holistic-harmony-area');
  if (!area) return;
  area.innerHTML = '';

  if (harmonyBlocks.length === 0) {
    const msg = document.createElement('span');
    msg.className = 'placeholder-text text-muted small';
    msg.textContent = 'Click a chord above to add it here…';
    area.appendChild(msg);
    return;
  }

  harmonyBlocks.forEach((b, i) => {
    const el = document.createElement('div');
    el.className = 'chord-block' + (i === harmSelectedIdx ? ' selected' : '');
    const durLabel = {w:'whole',h:'half',q:'qtr','8':'8th','16':'16th'}[b.duration] || b.duration;
    el.textContent = formatChordName(b, harmNotationMode, KEY_SIGNATURE);
    el.title = durLabel;
    el.addEventListener('click', () => {
      harmSelectedIdx = (harmSelectedIdx === i) ? null : i;
      renderHarmonyArea();
      renderHarmonyModifier();
    });
    area.appendChild(el);
  });
}

function renderHarmonyModifier() {
  const panel = document.getElementById('holistic-modifier-panel');
  if (!panel) return;

  if (harmSelectedIdx === null || harmSelectedIdx >= harmonyBlocks.length) {
    panel.innerHTML = '<p class="text-muted small mb-0">Select a chord block above to modify it.</p>';
    return;
  }

  const chord = harmonyBlocks[harmSelectedIdx];
  let html = '<div class="modifier-panel">';

  html += `<div class="modifier-row">
    <span class="modifier-label">Chromatic:</span>
    <button class="btn btn-outline-secondary btn-sm" id="hmod-lower">♭ Lower</button>
    <button class="btn btn-outline-secondary btn-sm" id="hmod-raise">♯ Raise</button>
  </div>`;

  const qualities = ['major','minor','diminished','augmented'];
  html += `<div class="modifier-row"><span class="modifier-label">Quality:</span>`;
  qualities.forEach(q => {
    const active = chord.quality === q && !chord.sus ? ' active' : '';
    const label = {major:'maj',minor:'min',diminished:'dim',augmented:'aug'}[q];
    html += `<button class="btn btn-outline-secondary btn-sm${active}" data-hquality="${q}">${label}</button>`;
  });
  html += `</div>`;

  if (UNLOCK_SUS) {
    html += `<div class="modifier-row"><span class="modifier-label">Sus:</span>`;
    ['sus2','sus4'].forEach(s => {
      const active = chord.sus === s ? ' active' : '';
      html += `<button class="btn btn-outline-secondary btn-sm${active}" data-hsus="${s}">${s}</button>`;
    });
    html += `</div>`;
  }

  if (UNLOCK_SEVENTH) {
    html += `<div class="modifier-row"><span class="modifier-label">Seventh:</span>`;
    const seventhOpts = [
      { val: 'major7', label: 'maj7' },
      { val: 'minor7', label: 'min7' },
    ];
    if (chord.quality === 'diminished') seventhOpts.push({ val: 'diminished7', label: 'dim7' });
    seventhOpts.forEach(opt => {
      const active = chord.seventh === opt.val ? ' active' : '';
      html += `<button class="btn btn-outline-secondary btn-sm${active}" data-hseventh="${opt.val}">${opt.label}</button>`;
    });
    html += `</div>`;
  }

  if (UNLOCK_EXTENSIONS) {
    html += `<div class="modifier-row"><span class="modifier-label">Extensions:</span>`;
    ['9','b9','#9','11','#11','13','b13'].forEach(ext => {
      const active = (chord.extensions || []).includes(ext) ? ' active' : '';
      html += `<button class="btn btn-outline-secondary btn-sm${active}" data-hext="${ext}">${ext.replace('b','♭').replace('#','♯')}</button>`;
    });
    html += `</div>`;
  }

  html += `<div class="modifier-row"><span class="modifier-label">Bass:</span>`;
  const chordTones = computeChordTones(chord);
  for (let pc = 0; pc < 12; pc++) {
    const isChordTone = chordTones.includes(pc);
    const active = chord.bass_pc === pc ? ' active' : '';
    const nonChord = !isChordTone ? ' non-chord' : '';
    html += `<button class="btn btn-outline-secondary btn-sm bass-btn${nonChord}${active}" data-hbass="${pc}">${noteNameForPc(pc, KEY_SIGNATURE)}</button>`;
  }
  html += `</div>`;

  html += `<div class="modifier-row"><span class="modifier-label">Duration:</span>`;
  const durOptions = [
    {val:'w',label:'Whole'},{val:'h',label:'Half'},{val:'q',label:'Qtr'},
    {val:'8',label:'8th'},{val:'16',label:'16th'}
  ];
  durOptions.forEach(d => {
    const active = chord.duration === d.val ? ' active' : '';
    html += `<button class="btn btn-outline-secondary btn-sm${active}" data-hdur="${d.val}">${d.label}</button>`;
  });
  html += `</div>`;

  html += `<div class="modifier-row mt-2">
    <button class="btn btn-outline-danger btn-sm" id="hmod-remove">Remove This Chord</button>
  </div>`;

  html += '</div>';
  panel.innerHTML = html;

  panel.querySelector('#hmod-lower')?.addEventListener('click', () => harmChromaticShift(-1));
  panel.querySelector('#hmod-raise')?.addEventListener('click', () => harmChromaticShift(1));
  panel.querySelectorAll('[data-hquality]').forEach(btn => {
    btn.addEventListener('click', () => {
      const c = harmonyBlocks[harmSelectedIdx];
      let { seventh, sus } = c;
      sus = null;
      if (btn.dataset.hquality !== 'diminished' && seventh === 'diminished7') seventh = null;
      if (['minor','diminished','augmented'].includes(btn.dataset.hquality) && seventh === 'major7') seventh = null;
      harmonyBlocks[harmSelectedIdx] = { ...c, quality: btn.dataset.hquality, seventh, sus };
      renderHarmonyArea(); renderHarmonyModifier();
    });
  });
  panel.querySelectorAll('[data-hsus]').forEach(btn => {
    btn.addEventListener('click', () => {
      const c = harmonyBlocks[harmSelectedIdx];
      const newSus = c.sus === btn.dataset.hsus ? null : btn.dataset.hsus;
      harmonyBlocks[harmSelectedIdx] = { ...c, sus: newSus };
      renderHarmonyArea(); renderHarmonyModifier();
    });
  });
  panel.querySelectorAll('[data-hseventh]').forEach(btn => {
    btn.addEventListener('click', () => {
      const c = harmonyBlocks[harmSelectedIdx];
      const newSeventh = c.seventh === btn.dataset.hseventh ? null : btn.dataset.hseventh;
      harmonyBlocks[harmSelectedIdx] = { ...c, seventh: newSeventh };
      renderHarmonyArea(); renderHarmonyModifier();
    });
  });
  panel.querySelectorAll('[data-hext]').forEach(btn => {
    btn.addEventListener('click', () => {
      const c = harmonyBlocks[harmSelectedIdx];
      const exts = [...(c.extensions || [])];
      const pos = exts.indexOf(btn.dataset.hext);
      if (pos >= 0) exts.splice(pos, 1); else exts.push(btn.dataset.hext);
      harmonyBlocks[harmSelectedIdx] = { ...c, extensions: exts };
      renderHarmonyArea(); renderHarmonyModifier();
    });
  });
  panel.querySelectorAll('[data-hbass]').forEach(btn => {
    btn.addEventListener('click', () => {
      const c = harmonyBlocks[harmSelectedIdx];
      const pc = parseInt(btn.dataset.hbass);
      harmonyBlocks[harmSelectedIdx] = { ...c, bass_pc: pc, bass_name: noteNameForPc(pc, KEY_SIGNATURE) };
      renderHarmonyArea(); renderHarmonyModifier();
    });
  });
  panel.querySelectorAll('[data-hdur]').forEach(btn => {
    btn.addEventListener('click', () => {
      const c = harmonyBlocks[harmSelectedIdx];
      harmonyBlocks[harmSelectedIdx] = { ...c, duration: btn.dataset.hdur };
      renderHarmonyArea(); renderHarmonyModifier();
    });
  });
  panel.querySelector('#hmod-remove')?.addEventListener('click', () => {
    harmonyBlocks.splice(harmSelectedIdx, 1);
    harmSelectedIdx = harmonyBlocks.length > 0 ? Math.min(harmSelectedIdx, harmonyBlocks.length - 1) : null;
    renderHarmonyArea(); renderHarmonyModifier();
  });
}

function harmChromaticShift(direction) {
  const chord = harmonyBlocks[harmSelectedIdx];
  const newPc = (chord.root_pc + direction + 12) % 12;
  const scale = DIATONIC_SCALES[KEY_SIGNATURE] || DIATONIC_SCALES['C'];
  const isDiatonic = scale.includes(newPc);

  let newName, preferSharp;
  if (isDiatonic) {
    newName = noteNameForPc(newPc, KEY_SIGNATURE);
    preferSharp = null;
  } else if (direction > 0) {
    newName = SHARP_NAMES[newPc];
    preferSharp = true;
  } else {
    newName = FLAT_NAMES[newPc];
    preferSharp = false;
  }

  const newBassPc   = chord.bass_pc === chord.root_pc ? newPc  : chord.bass_pc;
  const newBassName = chord.bass_pc === chord.root_pc ? newName : chord.bass_name;

  harmonyBlocks[harmSelectedIdx] = {
    ...chord,
    root_pc:     newPc,
    root_name:   newName,
    prefer_sharp: preferSharp,
    bass_pc:     newBassPc,
    bass_name:   newBassName,
  };
  renderHarmonyArea();
  renderHarmonyModifier();
}

// ---------------------------------------------------------------------------
// Staff visibility toggles
// ---------------------------------------------------------------------------

function initVisibilityToggles() {
  document.querySelectorAll('.staff-visibility-check').forEach(cb => {
    cb.addEventListener('change', () => {
      const target = document.getElementById('staff-section-' + cb.dataset.lineKey);
      if (target) target.style.display = cb.checked ? '' : 'none';
    });
  });
}

// ---------------------------------------------------------------------------
// Key Reference
// ---------------------------------------------------------------------------

function initKeyReference() {
  const btn = document.getElementById('btn-key-ref');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const chords = HARM_KEY_REFERENCE[KEY_SIGNATURE]
      || (KEY_SIGNATURE.endsWith('m') ? HARM_KEY_REFERENCE['Am'] : HARM_KEY_REFERENCE['C']);
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-volume-up me-1"></i>Playing…';
    await window.playChordArray(chords, 72, () => {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-music-note-list me-1"></i>Key Reference';
    });
  });
}

// ---------------------------------------------------------------------------
// Submit
// ---------------------------------------------------------------------------

async function submitHolisticAttempt() {
  const btn = document.getElementById('btn-holistic-submit');
  if (btn) { btn.disabled = true; btn.textContent = 'Submitting…'; }

  const lines = {};

  // Collect melody line notes
  document.querySelectorAll('[data-stave-line-key]').forEach(el => {
    const lk = el.dataset.staveLineKey;
    lines[lk] = lineNotes[lk] || [];
  });

  // Harmony
  lines['harmony'] = harmonyBlocks;

  try {
    const response = await fetch('/holistic/submit/' + EXERCISE_ID, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lines }),
    });
    const data = await response.json();
    if (data.redirect) {
      window.location.href = data.redirect;
    } else {
      if (btn) { btn.disabled = false; btn.textContent = 'Submit'; }
      alert(data.error || 'Submission failed');
    }
  } catch (err) {
    console.error(err);
    if (btn) { btn.disabled = false; btn.textContent = 'Submit'; }
    alert('Network error. Please try again.');
  }
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  initWavPlayback();
  initKeyReference();
  initVisibilityToggles();
  initHarmonyPanel();

  // Render all melody stave containers
  document.querySelectorAll('[data-stave-line-key]').forEach(containerEl => {
    const lk   = containerEl.dataset.staveLineKey;
    const clef = containerEl.dataset.clef || 'treble';
    getEditor(lk);  // ensure state exists
    renderStaveForLine(lk, clef, containerEl);
    bindStaveControls(lk, clef, containerEl);
  });

  document.getElementById('btn-holistic-submit')?.addEventListener('click', submitHolisticAttempt);

  if (window.MidiInput) {
    MidiInput.onNoteOn(({ midi }) => {
      if (!hoveredMidiTarget) return;
      const { lineKey, clef, containerEl } = hoveredMidiTarget;
      placeMidiNoteOnStave(lineKey, clef, containerEl, midi);
    });
  }
});
