/**
 * rhythm_notation.js — VexFlow 4 notation editor for rhythmic dictation.
 *
 * Like notation.js, but for unpitched percussion:
 * - All notes placed at b/4 on a percussion-clef staff
 * - No pitch selection, no accidentals, no key signature, no drag
 * - Click synth (Tone.Synth) for playback instead of piano sampler
 *
 * Keyboard shortcuts (exercise page):
 *   3 = 16th   4 = 8th   5 = quarter   6 = half   7 = whole
 *   . = toggle dot   , = place rest   Ctrl+Z = undo
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
  const PROP_PAD    = 12;

  const PERC_KEY = 'b/4';   // single pitch for all notes/rests

  const DURATION_BEATS = {
    w: 4, h: 2, q: 1, '8': 0.5, '16': 0.25,
    wr: 4, hr: 2, qr: 1, '8r': 0.5, '16r': 0.25,
  };

  const GHOST_SHAPES = {
    w:    { rx: 8, ry: 5, fill: 'none', stroke: '#555' },
    h:    { rx: 7, ry: 5, fill: 'none', stroke: '#555' },
    q:    { rx: 6, ry: 4, fill: '#555', stroke: '#555' },
    '8':  { rx: 6, ry: 4, fill: '#555', stroke: '#555' },
    '16': { rx: 5, ry: 3, fill: '#555', stroke: '#555' },
  };

  // =========================================================================
  // Editor state
  // =========================================================================
  let userNotes        = [];
  let selectedDur      = 'q';
  let isDotted         = false;
  let currentBeats     = 0;
  let staveTopYs       = [];
  let staveMiddleYs    = [];
  let measureInfo      = [];
  let ghostEl          = null;
  let selectedNoteIdx  = null;
  let pointerStartPos  = null;

  // =========================================================================
  // Audio — Salamander Grand Piano sampler
  // =========================================================================
  let pianoSampler = null;
  let countInSynth = null;

  // Rhythm clicks: real piano C4 from the Salamander Grand Piano.
  // Only C4 is loaded since every rhythm note plays that one pitch.
  function getPianoSampler() {
    if (!pianoSampler) {
      pianoSampler = new Tone.Sampler({
        urls: { C4: 'C4.mp3' },
        release: 1.5,
        baseUrl: 'https://tonejs.github.io/audio/salamander/',
      }).toDestination();
    }
    return pianoSampler;
  }

  // Count-in click: short sine-wave tick — clearly distinct from the piano
  function getCountInSynth() {
    if (!countInSynth) {
      countInSynth = new Tone.Synth({
        oscillator: { type: 'sine' },
        envelope: { attack: 0.001, decay: 0.04, sustain: 0, release: 0.02 },
      }).toDestination();
    }
    return countInSynth;
  }

  // =========================================================================
  // Pure helpers
  // =========================================================================

  function getBeatsPerMeasure() {
    const top = (typeof TIME_SIG_TOP    !== 'undefined') ? TIME_SIG_TOP    : 4;
    const bot = (typeof TIME_SIG_BOTTOM !== 'undefined') ? TIME_SIG_BOTTOM : 4;
    return top * (4 / bot);
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

  function buildGhostPadding(usedBeats, VF) {
    let left = getBeatsPerMeasure() - usedBeats;
    if (left < 0.001) return [];
    const ghosts = [];
    const durMap = [
      { beats: 4, dur: 'w' }, { beats: 2, dur: 'h' }, { beats: 1, dur: 'q' },
      { beats: 0.5, dur: '8' }, { beats: 0.25, dur: '16' },
    ];
    for (const { beats, dur } of durMap) {
      while (left >= beats - 0.001) {
        ghosts.push(new VF.GhostNote({ duration: dur }));
        left -= beats;
      }
    }
    return ghosts;
  }

  function propX(mInfo, beatOffset) {
    return mInfo.noteStartX + PROP_PAD + (beatOffset / getBeatsPerMeasure()) * mInfo.noteWidth;
  }

  /**
   * Beat-aware beam builder — same algorithm as notation.js.
   * Groups consecutive beamable notes that fall within the same beat,
   * using noteBeats() from our note data rather than VexFlow ticks.
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

  function flashError() {
    const svg = document.querySelector('#notation-container svg');
    if (svg) {
      svg.style.outline = '2px solid #dc3545';
      setTimeout(() => { svg.style.outline = ''; }, 500);
    }
  }

  function findStaveRow(clickY) {
    for (const sy of staveTopYs) {
      if (clickY >= sy - 20 && clickY <= sy + 60) return sy;
    }
    return null;
  }

  function getMiddleY(topY) {
    const idx = staveTopYs.indexOf(topY);
    return idx >= 0 ? staveMiddleYs[idx] : topY + 20;
  }

  /**
   * Find the measure index for a given (mx, clickY) position.
   * Filters by both X range and the matching stave row (Y), so that clicking
   * on row 2 col 0 returns a row-2 measure rather than the row-1 col-0 measure
   * that shares the same X range.
   */
  function findMeasure(mx, clickY) {
    const sy = findStaveRow(clickY);
    if (!sy) return -1;
    for (let i = 0; i < measureInfo.length; i++) {
      const m = measureInfo[i];
      if (mx >= m.startX && mx <= m.endX && m.staveY === sy) return i;
    }
    return -1;
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

  function buildStaveNote(noteObj, style) {
    const isRest = noteObj.duration.endsWith('r');
    // Use 'd' suffix for dotted non-rests so VexFlow's tick count is correct.
    const vfDur = (noteObj.dotted && !isRest) ? noteObj.duration + 'd' : noteObj.duration;
    const sn = new VF.StaveNote({
      keys: [PERC_KEY],
      duration: vfDur,
      clef: 'percussion',
    });
    if (noteObj.dotted) sn.addModifier(new VF.Dot(), 0);
    if (style) sn.setStyle(style);
    return sn;
  }

  function renderStaves(containerEl, notes, numMeasures, interactive, styleMap) {
    const savedScroll = containerEl.scrollLeft;
    containerEl.innerHTML = '';
    staveTopYs    = [];
    staveMiddleYs = [];
    measureInfo   = [];

    const containerWidth = containerEl.clientWidth || 800;
    const numRows    = Math.ceil(numMeasures / MEASURES_PER_ROW);
    const colCount   = Math.min(numMeasures, MEASURES_PER_ROW);
    const bpm        = getBeatsPerMeasure();

    const measureGroups = splitIntoMeasures(notes);
    while (measureGroups.length < numMeasures) measureGroups.push([]);

    const maxFill    = measureGroups.reduce((m, mg) => {
      const used = mg.reduce((s, n) => s + noteBeats(n), 0);
      return Math.max(m, used / bpm);
    }, 0);
    const remaining  = Math.max(1 / (bpm * 4), 1 - maxFill);
    const densityMin = 80 + Math.ceil(24 / remaining);
    const staveWidth = Math.max(densityMin, 120, Math.floor((containerWidth - STAVE_X_PAD * 2) / colCount));
    const svgWidth   = Math.max(containerWidth, STAVE_X_PAD * 2 + colCount * staveWidth);
    const svgHeight  = ROW_OFFSET + numRows * ROW_HEIGHT;

    const renderer = new VF.Renderer(containerEl, VF.Renderer.Backends.SVG);
    renderer.resize(svgWidth, svgHeight);
    const ctx = renderer.getContext();

    let globalNoteIdx = 0;
    const tiesToDraw  = [];
    let   pendingTie  = null;  // { vfNote, row } — awaiting the tieEnd note in the next measure

    for (let i = 0; i < numMeasures; i++) {
      const row    = Math.floor(i / MEASURES_PER_ROW);
      const col    = i % MEASURES_PER_ROW;
      const staveY = ROW_OFFSET + row * ROW_HEIGHT;
      const staveX = STAVE_X_PAD + col * staveWidth;

      const stave = new VF.Stave(staveX, staveY, staveWidth);
      if (col === 0) stave.addClef('percussion');
      if (i   === 0) stave.addTimeSignature(getTimeSigString());
      stave.setContext(ctx).draw();

      const topLineY    = stave.getYForLine(0);
      const middleLineY = stave.getYForLine(2);
      const noteStartX  = stave.getNoteStartX();
      const noteEndX    = stave.getNoteEndX();
      const noteWidth   = Math.max(60, noteEndX - noteStartX - PROP_PAD * 2);

      // Only push each row's staveTopY once (multiple measures share the same row Y)
      if (col === 0) {
        staveTopYs.push(topLineY);
        staveMiddleYs.push(middleLineY);
      }

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
        const startIdx = globalNoteIdx;
        const vfNotes  = mNotes.map((n, j) => {
          const s = styleMap ? (styleMap[startIdx + j] || null) : null;
          return buildStaveNote(n, s);
        });

        // ---- Cross-measure tie resolution ----
        if (pendingTie) {
          if (vfNotes.length > 0 && mNotes[0] && mNotes[0].tieEnd && pendingTie.row === row) {
            tiesToDraw.push(new VF.StaveTie({
              first_note:    pendingTie.vfNote,
              last_note:     vfNotes[0],
              first_indices: [0],
              last_indices:  [0],
            }));
          }
          pendingTie = null;
        }
        if (vfNotes.length > 0 && mNotes[mNotes.length - 1].tieStart) {
          pendingTie = { vfNote: vfNotes[vfNotes.length - 1], row };
        }

        const ghosts       = buildGhostPadding(usedBeats, VF);
        const allTickables = [...vfNotes, ...ghosts];

        if (allTickables.length > 0) {
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

          new VF.Formatter()
            .joinVoices([voice])
            .format([voice], Math.max(60, noteEndX - noteStartX - 10));

          voice.draw(ctx, stave);
          beams.forEach(beam => beam.setContext(ctx).draw());

          if (ghosts.length > 0) {
            try { mInfo.nextNoteX = ghosts[0].getAbsoluteX(); } catch (_) {}
          }
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
    containerEl.scrollLeft = savedScroll;
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

  function fitsInCurrentMeasure(beats) {
    const bpm = getBeatsPerMeasure();
    const incomplete = measureInfo.find(m => !m.isFull);
    if (!incomplete) return true;
    return beats <= (bpm - incomplete.usedBeats) + 0.001;
  }

  function placeRest() {
    const restDur = selectedDur + 'r';
    const beats   = noteBeats({ duration: restDur, dotted: isDotted });
    const bTotal  = (typeof BEATS_TOTAL !== 'undefined') ? BEATS_TOTAL : Infinity;
    if (currentBeats + beats > bTotal + 0.001 || !fitsInCurrentMeasure(beats)) {
      flashError(); return;
    }
    userNotes.push({ duration: restDur, dotted: isDotted });
    currentBeats += beats;
    refresh();
  }

  // =========================================================================
  // Interaction handlers
  // =========================================================================

  function attachInteractionHandlers(containerEl) {
    const svg = containerEl.querySelector('svg');
    if (!svg) return;

    ensureGhost(svg);
    updateGhostShape();
    svg.style.touchAction = 'pan-x';

    // Tag rendered note elements for selection
    svg.querySelectorAll('.vf-stavenote').forEach((g, idx) => {
      g.setAttribute('data-note-idx', idx);
    });

    function showGhostAt(mx, my) {
      const topY = findStaveRow(my);
      if (!topY) { hideGhost(); return; }
      const mIdx = findMeasure(mx, my);
      if (mIdx < 0 || measureInfo[mIdx].isFull) { hideGhost(); return; }
      const mInfo = measureInfo[mIdx];
      const x = (mInfo.nextNoteX != null) ? mInfo.nextNoteX : propX(mInfo, mInfo.usedBeats);
      showGhost(x, getMiddleY(topY));
    }

    function placeNote() {
      selectedNoteIdx = null;   // deselect when placing a new note

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
        userNotes.push({ duration: firstSpec.duration,  dotted: firstSpec.dotted,  tieStart: true });
        userNotes.push({ duration: secondSpec.duration, dotted: secondSpec.dotted, tieEnd:   true });
        currentBeats += beats;
        refresh();
        return;
      }

      userNotes.push({ duration: selectedDur, dotted: isDotted });
      currentBeats += beats;
      refresh();
    }

    function onPointerStart(mx, my, targetEl) {
      pointerStartPos = { x: mx, y: my };
      const noteG = targetEl ? targetEl.closest('[data-note-idx]') : null;
      if (noteG) return; // potential selection — resolved on pointerEnd
      if (!findStaveRow(my)) return;
      showGhostAt(mx, my);
    }

    function onPointerEnd(mx, my, targetEl) {
      const startPos = pointerStartPos;
      pointerStartPos = null;

      const noteG = targetEl ? targetEl.closest('[data-note-idx]') : null;
      if (noteG && startPos) {
        const dx = mx - startPos.x, dy = my - startPos.y;
        if (Math.sqrt(dx * dx + dy * dy) <= 8) {
          const idx = parseInt(noteG.getAttribute('data-note-idx'), 10);
          hideGhost();
          if (idx >= 0 && idx < userNotes.length) {
            if (selectedNoteIdx === idx) deselectNote(); else selectNote(idx);
          }
          return;
        }
      }

      hideGhost();
      if (!findStaveRow(my)) return;
      const mIdx = findMeasure(mx, my);
      if (mIdx >= 0 && measureInfo[mIdx].isFull) { flashError(); return; }
      placeNote();
    }

    // --- Mouse events ---
    svg.addEventListener('mousemove', (e) => {
      const rect = svg.getBoundingClientRect();
      showGhostAt(e.clientX - rect.left, e.clientY - rect.top);
    });

    svg.addEventListener('mouseleave', hideGhost);

    svg.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;
      const rect = svg.getBoundingClientRect();
      onPointerStart(e.clientX - rect.left, e.clientY - rect.top, e.target);
    });

    svg.addEventListener('mouseup', (e) => {
      if (e.button !== 0) return;
      const rect = svg.getBoundingClientRect();
      onPointerEnd(e.clientX - rect.left, e.clientY - rect.top, e.target);
    });

    // --- Touch events ---
    let touchStartClient = null;

    svg.addEventListener('touchstart', (e) => {
      const t = e.touches[0];
      touchStartClient = { x: t.clientX, y: t.clientY };
      const rect = svg.getBoundingClientRect();
      onPointerStart(
        t.clientX - rect.left, t.clientY - rect.top,
        document.elementFromPoint(t.clientX, t.clientY)
      );
    }, { passive: true });

    svg.addEventListener('touchmove', (e) => {
      const t = e.touches[0];
      if (touchStartClient) {
        const dx = Math.abs(t.clientX - touchStartClient.x);
        const dy = Math.abs(t.clientY - touchStartClient.y);
        if (dx > dy && dx > 15) { hideGhost(); return; }
      }
      e.preventDefault();
      const rect = svg.getBoundingClientRect();
      showGhostAt(t.clientX - rect.left, t.clientY - rect.top);
    }, { passive: false });

    svg.addEventListener('touchend', (e) => {
      e.preventDefault();
      const t  = e.changedTouches[0];
      const sc = touchStartClient;
      touchStartClient = null;
      if (sc) {
        const dx = Math.abs(t.clientX - sc.x);
        const dy = Math.abs(t.clientY - sc.y);
        if (dx > dy && dx > 15) return;
      }
      const rect = svg.getBoundingClientRect();
      onPointerEnd(
        t.clientX - rect.left, t.clientY - rect.top,
        document.elementFromPoint(t.clientX, t.clientY)
      );
    }, { passive: false });
  }

  // =========================================================================
  // MIDI input (rhythmic dictation)
  // =========================================================================

  window.placeMidiRhythmNote = function () {
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
      userNotes.push({ duration: firstSpec.duration,  dotted: firstSpec.dotted,  tieStart: true });
      userNotes.push({ duration: secondSpec.duration, dotted: secondSpec.dotted, tieEnd:   true });
      currentBeats += beats;
      refresh();
      return;
    }

    userNotes.push({ duration: selectedDur, dotted: isDotted });
    currentBeats += beats;
    refresh();
  };

  // =========================================================================
  // Refresh
  // =========================================================================

  function refresh() {
    if (selectedNoteIdx !== null && selectedNoteIdx >= userNotes.length) {
      selectedNoteIdx = null;
    }
    const el = document.getElementById('notation-container');
    if (!el) return;
    // Highlight selected note in blue
    const styleMap = userNotes.map((_, i) =>
      i === selectedNoteIdx ? { fillStyle: '#2563eb', strokeStyle: '#2563eb' } : null
    );
    renderStaves(el, userNotes, NUM_MEASURES, true, styleMap);
    attachInteractionHandlers(el);
    updateSelectionToolbar();
  }

  // =========================================================================
  // Public API
  // =========================================================================

  window.renderReadOnlyRhythmStave = function (containerId, notes) {
    const el = document.getElementById(containerId);
    if (!el || !VF) return;
    const bpm = getBeatsPerMeasure();
    const n   = notes.length
      ? Math.max(1, Math.ceil(notes.reduce((s, n) => s + noteBeats(n), 0) / bpm))
      : 1;
    renderStaves(el, notes, n, false, null);
  };

  window.renderStyledRhythmStave = function (containerId, notes, styleMap) {
    const el = document.getElementById(containerId);
    if (!el || !VF) return;
    const bpm = getBeatsPerMeasure();
    const n   = notes.length
      ? Math.max(1, Math.ceil(notes.reduce((s, n) => s + noteBeats(n), 0) / bpm))
      : 1;
    renderStaves(el, notes, n, false, styleMap);
  };

  /**
   * Play a rhythm note array using the click synth.
   * @param {Array}         notes   [{duration[, dotted]}, ...]
   * @param {number}        bpm     tempo in BPM
   * @param {function|null} onDone  callback when finished
   */
  window.playRhythmArray = async function (notes, bpm, onDone, options) {
    if (typeof Tone === 'undefined') return;
    await Tone.start();
    const piano      = getPianoSampler();
    const countSynth = getCountInSynth();
    await Tone.loaded();   // wait for the C4 sample to finish downloading
    Tone.Transport.cancel();
    const secPerBeat = 60 / (bpm || 100);
    let t = Tone.Transport.seconds;

    // --- Count-in: one measure of straight beats ---
    // Compound meters (6/8, 9/8, 12/8): beat = dotted quarter (1.5 q-units)
    // Simple meters: beat = quarter note
    if (!options || !options.skipCountIn) {
      const top = (typeof TIME_SIG_TOP    !== 'undefined') ? TIME_SIG_TOP    : 4;
      const bot = (typeof TIME_SIG_BOTTOM !== 'undefined') ? TIME_SIG_BOTTOM : 4;
      const isCompound    = (bot === 8);
      const countBeats    = isCompound ? top / 3 : top;
      const countBeatSec  = isCompound ? secPerBeat * 1.5 : secPerBeat;

      for (let i = 0; i < countBeats; i++) {
        Tone.Transport.schedule(time => {
          countSynth.triggerAttackRelease('A5', '32n', time);
        }, t);
        t += countBeatSec;
      }
    }

    // --- Rhythm playback ---
    // Rules:
    //  • tieEnd  → no click; time advances silently (the tieStart note already
    //              covered its duration with an extended sound)
    //  • tieStart → click once; sound duration spans BOTH tied notes
    //  • normal note → click once; sound duration = 88 % of note value
    //                  (makes a long note audibly ring out vs a short note)
    notes.forEach((n, idx) => {
      const baseBeats = DURATION_BEATS[n.duration] || 1;
      const beats     = n.dotted ? baseBeats * 1.5 : baseBeats;
      const isRest    = n.duration.endsWith('r');

      if (n.tieEnd) {
        // Silent continuation — just advance the clock
        t += beats * secPerBeat;
        return;
      }

      if (!isRest) {
        // How long should this click ring? For a tieStart, add the tieEnd's beats.
        let soundBeats = beats;
        if (n.tieStart && idx + 1 < notes.length && notes[idx + 1].tieEnd) {
          const nxt = notes[idx + 1];
          const nb  = DURATION_BEATS[nxt.duration] || 1;
          soundBeats += nxt.dotted ? nb * 1.5 : nb;
        }
        const soundSec = soundBeats * secPerBeat * 0.88;
        Tone.Transport.schedule(time => {
          piano.triggerAttackRelease('C4', soundSec, time);
        }, t);
      }
      t += beats * secPerBeat;
    });

    if (onDone) Tone.Transport.schedule(() => onDone(), t + 0.3);
    Tone.Transport.start();
  };

  // =========================================================================
  // DOMContentLoaded
  // =========================================================================
  document.addEventListener('DOMContentLoaded', () => {
    const vfError = initVexFlow();
    if (vfError) {
      console.error('[rhythm_notation.js]', vfError);
      const c = document.getElementById('notation-container');
      if (c) c.innerHTML =
        `<div class="alert alert-danger m-2"><strong>Notation error:</strong> ${vfError}</div>`;
    }

    const container = document.getElementById('notation-container');
    if (container && !vfError) refresh();

    document.querySelectorAll('.duration-btn').forEach(btn => {
      btn.addEventListener('click', () => setDuration(btn.dataset.dur));
    });

    document.getElementById('btn-dot')?.addEventListener('click', toggleDot);
    document.getElementById('btn-place-rest')?.addEventListener('click', placeRest);

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

    document.getElementById('btn-clear')?.addEventListener('click', () => {
      userNotes = []; currentBeats = 0; selectedNoteIdx = null; refresh();
    });

    document.getElementById('btn-sel-deselect')?.addEventListener('click', deselectNote);

    document.getElementById('btn-submit')?.addEventListener('click', async () => {
      if (!userNotes.length) { alert('Place at least one note before submitting.'); return; }
      const btn = document.getElementById('btn-submit');
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Grading…';
      try {
        const res  = await fetch(`/rhythm/submit/${RHYTHM_ID}`, {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({ notes: userNotes }),
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

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' ||
          e.target.isContentEditable) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (!document.getElementById('notation-container')) return;

      switch (e.key) {
        case '3': setDuration('16'); e.preventDefault(); break;
        case '4': setDuration('8');  e.preventDefault(); break;
        case '5': setDuration('q');  e.preventDefault(); break;
        case '6': setDuration('h');  e.preventDefault(); break;
        case '7': setDuration('w');  e.preventDefault(); break;
        case '.': toggleDot();       e.preventDefault(); break;
        case ',': placeRest();       e.preventDefault(); break;
      }
    });

    // Results page
    if (typeof CORRECT_NOTES !== 'undefined' && typeof USER_NOTES !== 'undefined') {
      window.renderReadOnlyRhythmStave('correct-staff', CORRECT_NOTES);

      const styleMap = USER_NOTES.map((un, i) => {
        if (i >= CORRECT_NOTES.length) return { fillStyle: 'red', strokeStyle: 'red' };
        const cn    = CORRECT_NOTES[i];
        const durOk = un.duration === cn.duration;
        return durOk ? null : { fillStyle: 'red', strokeStyle: 'red' };
      });
      window.renderStyledRhythmStave('user-staff', USER_NOTES, styleMap);
    }
  });
})();
