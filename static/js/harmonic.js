// harmonic.js — Chord builder interface for Harmonic Dictation
// Depends on: chord_block_utils.js (loaded before this), Tone.js, player.js
// Template variables expected: PROGRESSION_ID, MIDI_URL, KEY_SIGNATURE,
//   PROGRESSION_TEMPO, UNLOCK_SEVENTH, UNLOCK_EXTENSIONS, UNLOCK_SUS,
//   SHOW_CHORD_COUNT, NUM_CHORDS

'use strict';

// ---------------------------------------------------------------------------
// Shortcuts into ChordBlockUtils (loaded before this file)
// ---------------------------------------------------------------------------
const {
  SHARP_NAMES, FLAT_NAMES, FLAT_KEYS, noteNameForPc,
  DIATONIC_SCALES, DIATONIC_QUALITIES_MAJOR, DIATONIC_QUALITIES_MINOR,
  QUALITY_INTERVALS, HARM_KEY_REFERENCE,
  formatChordName, computeChordTones,
} = window.ChordBlockUtils;

// Alias: harmonic.js historically called this getChordTones
function getChordTones(chord) { return computeChordTones(chord); }

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let notationMode = 'roman';    // 'roman' | 'nashville' | 'lead'
let blocks       = [];          // array of chord objects
let selectedIdx  = null;        // index of currently selected block

// ---------------------------------------------------------------------------
// Diatonic palette
// ---------------------------------------------------------------------------

function buildDiatonicPalette() {
  const container = document.getElementById('diatonic-palette');
  if (!container) return;
  container.innerHTML = '';

  const scale = DIATONIC_SCALES[KEY_SIGNATURE] || DIATONIC_SCALES['C'];
  const isMinor = KEY_SIGNATURE.endsWith('m');
  const qualities = isMinor ? DIATONIC_QUALITIES_MINOR : DIATONIC_QUALITIES_MAJOR;

  scale.forEach((pc, idx) => {
    const quality = qualities[idx];
    const chord = makeChord(pc, quality);
    const label = formatChordName(chord, notationMode, KEY_SIGNATURE);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-outline-secondary palette-btn';
    btn.textContent = label;
    btn.dataset.pc = pc;
    btn.dataset.quality = quality;
    btn.addEventListener('click', () => addBlock(makeChord(pc, quality)));
    container.appendChild(btn);
  });
}

function makeChord(rootPc, quality) {
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
  };
}

// ---------------------------------------------------------------------------
// Block management
// ---------------------------------------------------------------------------

function addBlock(chord) {
  // If show_chord_count mode and there are still placeholders to fill, replace
  if (SHOW_CHORD_COUNT && blocks.length < NUM_CHORDS) {
    blocks.push(chord);
  } else if (!SHOW_CHORD_COUNT) {
    blocks.push(chord);
  } else {
    // All slots filled, still allow adding (extra)
    blocks.push(chord);
  }
  selectedIdx = blocks.length - 1;
  render();
}

function renderBuildingArea() {
  const area = document.getElementById('chord-building-area');
  if (!area) return;
  area.innerHTML = '';

  if (SHOW_CHORD_COUNT) {
    const total = Math.max(NUM_CHORDS, blocks.length);
    for (let i = 0; i < total; i++) {
      if (i < blocks.length) {
        area.appendChild(makeBlockEl(i, blocks[i]));
      } else {
        // Placeholder
        const ph = document.createElement('div');
        ph.className = 'chord-placeholder';
        ph.textContent = '?';
        area.appendChild(ph);
      }
    }
  } else {
    if (blocks.length === 0) {
      const msg = document.createElement('span');
      msg.className = 'placeholder-text';
      msg.textContent = 'Click a chord above to add it here…';
      area.appendChild(msg);
    } else {
      blocks.forEach((b, i) => area.appendChild(makeBlockEl(i, b)));
    }
  }
}

function makeBlockEl(i, chord) {
  const el = document.createElement('div');
  el.className = 'chord-block' + (i === selectedIdx ? ' selected' : '');
  el.textContent = formatChordName(chord, notationMode, KEY_SIGNATURE);
  el.addEventListener('click', () => {
    selectedIdx = (selectedIdx === i) ? null : i;
    render();
  });
  return el;
}

// ---------------------------------------------------------------------------
// Modifier panel
// ---------------------------------------------------------------------------

function renderModifierPanel() {
  const panel = document.getElementById('modifier-panel');
  if (!panel) return;

  if (selectedIdx === null || selectedIdx >= blocks.length) {
    panel.innerHTML = '<p class="text-muted small mb-0">Select a chord block above to modify it.</p>';
    return;
  }

  const chord = blocks[selectedIdx];
  let html = '<div class="modifier-panel">';

  // Chromatic raise/lower
  html += `<div class="modifier-row">
    <span class="modifier-label">Chromatic:</span>
    <button class="btn btn-outline-secondary btn-sm" id="mod-lower">♭ Lower</button>
    <button class="btn btn-outline-secondary btn-sm" id="mod-raise">♯ Raise</button>
  </div>`;

  // Quality
  const qualities = ['major','minor','diminished','augmented'];
  html += `<div class="modifier-row"><span class="modifier-label">Quality:</span>`;
  qualities.forEach(q => {
    const active = chord.quality === q && !chord.sus ? ' active' : '';
    const label = {major:'maj',minor:'min',diminished:'dim',augmented:'aug'}[q];
    html += `<button class="btn btn-outline-secondary btn-sm${active}" data-quality="${q}">${label}</button>`;
  });
  html += `</div>`;

  // Sus (only if progression contains sus chords)
  if (UNLOCK_SUS) {
    html += `<div class="modifier-row"><span class="modifier-label">Sus:</span>`;
    ['sus2','sus4'].forEach(s => {
      const active = chord.sus === s ? ' active' : '';
      html += `<button class="btn btn-outline-secondary btn-sm${active}" data-sus="${s}">${s}</button>`;
    });
    html += `</div>`;
  }

  // Seventh (only if unlocked)
  if (UNLOCK_SEVENTH) {
    html += `<div class="modifier-row"><span class="modifier-label">Seventh:</span>`;
    const seventhOpts = [
      { val: 'major7', label: 'maj7' },
      { val: 'minor7', label: 'min7' },
    ];
    if (chord.quality === 'diminished') {
      seventhOpts.push({ val: 'diminished7', label: 'dim7' });
    }
    seventhOpts.forEach(opt => {
      const active = chord.seventh === opt.val ? ' active' : '';
      html += `<button class="btn btn-outline-secondary btn-sm${active}" data-seventh="${opt.val}">${opt.label}</button>`;
    });
    html += `</div>`;
  }

  // Extensions (only if unlocked)
  if (UNLOCK_EXTENSIONS) {
    html += `<div class="modifier-row"><span class="modifier-label">Extensions:</span>`;
    ['9','b9','#9','11','#11','13','b13'].forEach(ext => {
      const active = (chord.extensions || []).includes(ext) ? ' active' : '';
      const label  = ext.replace('b','♭').replace('#','♯');
      html += `<button class="btn btn-outline-secondary btn-sm${active}" data-ext="${ext}">${label}</button>`;
    });
    html += `</div>`;
  }

  // Bass note
  html += `<div class="modifier-row"><span class="modifier-label">Bass:</span>`;
  const chordTones = getChordTones(chord);
  for (let pc = 0; pc < 12; pc++) {
    const isChordTone = chordTones.includes(pc);
    const active = chord.bass_pc === pc ? ' active' : '';
    const nonChord = !isChordTone ? ' non-chord' : '';
    const noteName = noteNameForPc(pc, KEY_SIGNATURE);
    html += `<button class="btn btn-outline-secondary btn-sm bass-btn${nonChord}${active}" data-bass="${pc}">${noteName}</button>`;
  }
  html += `</div>`;

  // Remove block button
  html += `<div class="modifier-row mt-2">
    <button class="btn btn-outline-danger btn-sm" id="mod-remove">Remove This Chord</button>
  </div>`;

  html += '</div>';
  panel.innerHTML = html;

  // Attach events
  panel.querySelector('#mod-lower')?.addEventListener('click', () => {
    chromaticShift(selectedIdx, -1);
  });
  panel.querySelector('#mod-raise')?.addEventListener('click', () => {
    chromaticShift(selectedIdx, 1);
  });
  panel.querySelectorAll('[data-quality]').forEach(btn => {
    btn.addEventListener('click', () => setQuality(selectedIdx, btn.dataset.quality));
  });
  panel.querySelectorAll('[data-sus]').forEach(btn => {
    btn.addEventListener('click', () => setSus(selectedIdx, btn.dataset.sus));
  });
  panel.querySelectorAll('[data-seventh]').forEach(btn => {
    btn.addEventListener('click', () => setSeventh(selectedIdx, btn.dataset.seventh));
  });
  panel.querySelectorAll('[data-ext]').forEach(btn => {
    btn.addEventListener('click', () => toggleExtension(selectedIdx, btn.dataset.ext));
  });
  panel.querySelectorAll('.bass-btn').forEach(btn => {
    btn.addEventListener('click', () => setBass(selectedIdx, parseInt(btn.dataset.bass)));
  });
  panel.querySelector('#mod-remove')?.addEventListener('click', () => {
    blocks.splice(selectedIdx, 1);
    selectedIdx = blocks.length > 0 ? Math.min(selectedIdx, blocks.length - 1) : null;
    render();
  });
}

// ---------------------------------------------------------------------------
// Modifier actions
// ---------------------------------------------------------------------------

function chromaticShift(idx, direction) {
  const chord = blocks[idx];
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

  blocks[idx] = {
    ...chord,
    root_pc:     newPc,
    root_name:   newName,
    prefer_sharp: preferSharp,
    bass_pc:     newBassPc,
    bass_name:   newBassName,
  };
  render();
}

function setQuality(idx, quality) {
  const chord = blocks[idx];
  let { seventh, sus } = chord;
  sus = null;
  if (quality !== 'diminished' && seventh === 'diminished7') seventh = null;
  if (['minor','diminished','augmented'].includes(quality) && seventh === 'major7') seventh = null;
  blocks[idx] = { ...chord, quality, seventh, sus };
  render();
}

function setSus(idx, susVal) {
  const chord = blocks[idx];
  const newSus = chord.sus === susVal ? null : susVal;
  blocks[idx] = { ...chord, sus: newSus };
  render();
}

function setSeventh(idx, seventh) {
  const chord = blocks[idx];
  const newSeventh = chord.seventh === seventh ? null : seventh;
  blocks[idx] = { ...chord, seventh: newSeventh };
  render();
}

function toggleExtension(idx, ext) {
  const chord = blocks[idx];
  const exts = [...(chord.extensions || [])];
  const pos = exts.indexOf(ext);
  if (pos >= 0) exts.splice(pos, 1);
  else exts.push(ext);
  blocks[idx] = { ...chord, extensions: exts };
  render();
}

function setBass(idx, pc) {
  const chord = blocks[idx];
  blocks[idx] = { ...chord, bass_pc: pc, bass_name: noteNameForPc(pc, KEY_SIGNATURE) };
  render();
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

function render() {
  buildDiatonicPalette();
  renderBuildingArea();
  renderModifierPanel();
}

// ---------------------------------------------------------------------------
// Notation mode toggle
// ---------------------------------------------------------------------------

function setNotationMode(mode) {
  notationMode = mode;
  document.querySelectorAll('.notation-toggle-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });
  render();
}

// ---------------------------------------------------------------------------
// Submit
// ---------------------------------------------------------------------------

async function submitAnswer() {
  const btn = document.getElementById('btn-submit');
  btn.disabled = true;
  btn.textContent = 'Submitting…';

  try {
    const response = await fetch(`/harmonic/submit/${PROGRESSION_ID}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chords: blocks }),
    });
    const data = await response.json();
    if (data.redirect) {
      window.location.href = data.redirect;
    } else {
      btn.disabled = false;
      btn.textContent = 'Submit';
      alert(data.error || 'Submission failed');
    }
  } catch (err) {
    btn.disabled = false;
    btn.textContent = 'Submit';
    console.error(err);
  }
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  // Notation toggles
  document.querySelectorAll('.notation-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => setNotationMode(btn.dataset.mode));
  });

  // Undo / Clear
  document.getElementById('btn-undo')?.addEventListener('click', () => {
    if (blocks.length) {
      blocks.pop();
      if (selectedIdx !== null && selectedIdx >= blocks.length) {
        selectedIdx = blocks.length > 0 ? blocks.length - 1 : null;
      }
      render();
    }
  });
  document.getElementById('btn-clear')?.addEventListener('click', () => {
    blocks = [];
    selectedIdx = null;
    render();
  });

  // Submit
  document.getElementById('btn-submit')?.addEventListener('click', submitAnswer);

  // Key Reference
  const btnKeyRef = document.getElementById('btn-key-ref');
  if (btnKeyRef) {
    btnKeyRef.addEventListener('click', async () => {
      const chords = HARM_KEY_REFERENCE[KEY_SIGNATURE]
        || (KEY_SIGNATURE.endsWith('m') ? HARM_KEY_REFERENCE['Am'] : HARM_KEY_REFERENCE['C']);
      btnKeyRef.disabled = true;
      btnKeyRef.innerHTML = '<i class="bi bi-volume-up me-1"></i>Playing…';
      await window.playChordArray(chords, 72, () => {
        btnKeyRef.disabled = false;
        btnKeyRef.innerHTML = '<i class="bi bi-music-note-list me-1"></i>Key Reference';
      });
    });
  }

  // Initial render
  render();
});
