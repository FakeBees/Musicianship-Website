/* Debug mode — screen name + permission level.
 *
 * Toggle with the key combo below. Debug mode persists across page loads and
 * tabs (localStorage).
 *
 * Renders an in-page floating panel. That is deliberate: browsers provide no
 * way to keep a separate window on top — there is no always-on-top API, and
 * window.focus() on a background popup is ignored by Chrome and Safari. An
 * in-page panel is above the page by construction, survives navigation, and
 * never has to fight for focus. A "Pop out" button is still there when you
 * want the panel on a second monitor.
 *
 * ── Why not fn+D ──────────────────────────────────────────────────────────
 * The `fn` key is not visible to JavaScript. KeyboardEvent exposes ctrlKey,
 * shiftKey, altKey and metaKey — there is no fnKey, in any browser. macOS
 * handles fn at the hardware/OS layer, so fn+D reaches the page as a bare `d`
 * keypress, indistinguishable from typing the letter. Binding bare `d` would
 * fire while typing in the notation editor and every admin form.
 *
 * To change the combo, edit MATCHES_TOGGLE below. Some alternatives:
 *   Ctrl+Shift+D  e.ctrlKey && e.shiftKey && e.code === 'KeyD'   (current)
 *   Alt+D         e.altKey && e.code === 'KeyD'
 *   F9            e.code === 'F9'
 *   backtick      e.code === 'Backquote' && !e.ctrlKey && !e.metaKey
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'musicianship.debugMode';
  var SCREEN_KEY  = 'musicianship.debugScreen';
  var POS_KEY     = 'musicianship.debugPos';
  var COLLAPSE_KEY = 'musicianship.debugCollapsed';
  var WINDOW_NAME = 'musicianshipDebug';
  var COMBO_LABEL = 'Ctrl+Shift+D';
  var PANEL_ID    = 'mt-debug-panel';

  function MATCHES_TOGGLE(e) {
    return e.ctrlKey && e.shiftKey && !e.metaKey && e.code === 'KeyD';
  }

  // ── Storage helpers (all guarded — private mode can throw) ───────────────
  function get(k)    { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* ignore */ } }

  function isOn()        { return get(STORAGE_KEY) === 'on'; }
  function isCollapsed() { return get(COLLAPSE_KEY) === 'yes'; }

  function screenMeta() {
    var el = document.getElementById('screen-meta');
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  }

  /* Publish the current screen so a popped-out window can follow along via the
   * storage event. Written on every load regardless of debug state. */
  function publishScreen() {
    var meta = screenMeta();
    if (!meta) return;
    meta.publishedAt = Date.now();
    set(SCREEN_KEY, JSON.stringify(meta));
  }

  // ── Styles ───────────────────────────────────────────────────────────────
  var CSS = [
    '#' + PANEL_ID + '{position:fixed;z-index:2147483000;width:330px;',
      'background:#16181c;color:#e6e8eb;border:1px solid #2f343d;border-radius:9px;',
      'font:11.5px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;',
      'box-shadow:0 8px 28px rgba(0,0,0,.45);overflow:hidden;}',
    '#' + PANEL_ID + ' *{box-sizing:border-box;margin:0;padding:0;}',
    '#' + PANEL_ID + ' .mtd-head{display:flex;align-items:center;gap:6px;',
      'padding:7px 9px;background:#20242c;border-bottom:1px solid #2f343d;cursor:move;',
      'user-select:none;}',
    '#' + PANEL_ID + ' .mtd-dot{width:7px;height:7px;border-radius:50%;background:#b85450;',
      'flex-shrink:0;}',
    '#' + PANEL_ID + ' .mtd-title{font-size:10px;letter-spacing:.09em;text-transform:uppercase;',
      'color:#8b93a1;font-weight:600;flex:1;}',
    '#' + PANEL_ID + ' .mtd-btn{background:none;border:1px solid #3a404b;color:#8b93a1;',
      'border-radius:4px;font:inherit;font-size:10px;padding:1px 6px;cursor:pointer;}',
    '#' + PANEL_ID + ' .mtd-btn:hover{color:#e6e8eb;border-color:#5a6272;}',
    '#' + PANEL_ID + ' .mtd-body{padding:10px 11px;max-height:70vh;overflow-y:auto;}',
    '#' + PANEL_ID + ' .mtd-name{font-size:15px;font-weight:700;color:#fff;',
      'word-break:break-all;line-height:1.25;}',
    '#' + PANEL_ID + ' .mtd-path{color:#8b93a1;font-size:10.5px;margin-top:2px;',
      'word-break:break-all;}',
    '#' + PANEL_ID + ' .mtd-sec{margin-top:9px;padding-top:8px;border-top:1px solid #262b33;}',
    '#' + PANEL_ID + ' .mtd-row{display:flex;gap:8px;padding:1.5px 0;}',
    '#' + PANEL_ID + ' .mtd-k{color:#8b93a1;min-width:74px;flex-shrink:0;}',
    '#' + PANEL_ID + ' .mtd-v{color:#e6e8eb;word-break:break-word;}',
    '#' + PANEL_ID + ' .mtd-pill{display:inline-block;padding:1px 8px;border-radius:999px;',
      'font-size:10px;font-weight:700;color:#12141a;}',
    '#' + PANEL_ID + ' .mtd-note{color:#8b93a1;font-size:10.5px;line-height:1.45;',
      'margin-top:6px;border-left:2px solid #2f343d;padding-left:8px;}',
    '#' + PANEL_ID + ' .mtd-yes{color:#82b366;font-weight:700;}',
    '#' + PANEL_ID + ' .mtd-no{color:#d97b7b;font-weight:700;}',
    '#' + PANEL_ID + '.mtd-collapsed .mtd-body{display:none;}',
    '#' + PANEL_ID + '.mtd-collapsed{width:auto;}',
    '#' + PANEL_ID + '.mtd-collapsed .mtd-head{cursor:pointer;}',
    '#' + PANEL_ID + ' .mtd-chip{color:#fff;font-weight:700;font-size:11px;}'
  ].join('');

  function ensureStyles() {
    if (document.getElementById('mt-debug-style')) return;
    var s = document.createElement('style');
    s.id = 'mt-debug-style';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  // ── Panel ────────────────────────────────────────────────────────────────
  function removePanel() {
    var el = document.getElementById(PANEL_ID);
    if (el) el.remove();
  }

  function yesno(v) {
    return '<span class="' + (v ? 'mtd-yes' : 'mtd-no') + '">' + (v ? 'YES' : 'NO') + '</span>';
  }

  function esc(s) {
    return String(s === null || s === undefined || s === '' ? '—' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function buildPanel(meta) {
    ensureStyles();
    removePanel();

    var panel = document.createElement('div');
    panel.id = PANEL_ID;
    if (isCollapsed()) panel.className = 'mtd-collapsed';

    var pos = null;
    try { pos = JSON.parse(get(POS_KEY)); } catch (e) { /* ignore */ }
    if (pos && typeof pos.left === 'number') {
      panel.style.left = pos.left + 'px';
      panel.style.top  = pos.top + 'px';
    } else {
      panel.style.left = '12px';
      panel.style.bottom = '12px';
    }

    panel.innerHTML =
      '<div class="mtd-head">' +
        '<span class="mtd-dot"></span>' +
        '<span class="mtd-title mtd-titletext">debug</span>' +
        '<button class="mtd-btn mtd-pop" title="Open in a separate window">Pop out</button>' +
        '<button class="mtd-btn mtd-min" title="Collapse">–</button>' +
      '</div>' +
      '<div class="mtd-body">' +
        '<div class="mtd-name"></div><div class="mtd-path"></div>' +
        '<div class="mtd-sec mtd-screen"></div>' +
        '<div class="mtd-sec mtd-access"></div>' +
        '<div class="mtd-sec mtd-viewer"></div>' +
      '</div>';

    document.body.appendChild(panel);
    wireHeader(panel);
    renderScreen(panel, meta);
    fetchViewer(panel, meta);
    clampIntoView(panel);
    return panel;
  }

  /* Keep the whole panel on screen — not just its header. Without this, a panel
   * dragged near the bottom edge renders its body below the fold when expanded,
   * and a window resize can strand it off screen entirely. */
  function clampIntoView(panel) {
    if (panel.style.top === '' || panel.style.top === 'auto') return; // bottom-anchored
    var r = panel.getBoundingClientRect();
    var maxTop  = Math.max(8, window.innerHeight - r.height - 8);
    var maxLeft = Math.max(8, window.innerWidth  - r.width  - 8);
    panel.style.top  = Math.max(8, Math.min(maxTop,  r.top))  + 'px';
    panel.style.left = Math.max(8, Math.min(maxLeft, r.left)) + 'px';
  }

  function wireHeader(panel) {
    var head = panel.querySelector('.mtd-head');

    panel.querySelector('.mtd-pop').addEventListener('click', function (e) {
      e.stopPropagation();
      openPopout();
    });

    panel.querySelector('.mtd-min').addEventListener('click', function (e) {
      e.stopPropagation();
      setCollapsed(panel, !panel.classList.contains('mtd-collapsed'));
    });

    head.addEventListener('click', function () {
      if (panel.classList.contains('mtd-collapsed')) setCollapsed(panel, false);
    });

    // Drag by the header.
    var dragging = false, offX = 0, offY = 0;
    head.addEventListener('mousedown', function (e) {
      if (e.target.classList.contains('mtd-btn')) return;
      var r = panel.getBoundingClientRect();
      dragging = true;
      offX = e.clientX - r.left;
      offY = e.clientY - r.top;
      panel.style.bottom = 'auto';
      panel.style.left = r.left + 'px';
      panel.style.top  = r.top + 'px';
      document.body.style.userSelect = 'none';   // don't select page text mid-drag
      e.preventDefault();
    });
    document.addEventListener('mousemove', function (e) {
      if (!dragging) return;
      var r = panel.getBoundingClientRect();
      var maxLeft = Math.max(8, window.innerWidth  - r.width  - 8);
      var maxTop  = Math.max(8, window.innerHeight - r.height - 8);
      panel.style.left = Math.max(8, Math.min(maxLeft, e.clientX - offX)) + 'px';
      panel.style.top  = Math.max(8, Math.min(maxTop,  e.clientY - offY)) + 'px';
    });
    document.addEventListener('mouseup', function () {
      if (!dragging) return;
      dragging = false;
      document.body.style.userSelect = '';
      clampIntoView(panel);
      var r = panel.getBoundingClientRect();
      set(POS_KEY, JSON.stringify({ left: Math.round(r.left), top: Math.round(r.top) }));
    });

    window.addEventListener('resize', function () { clampIntoView(panel); });
  }

  function setCollapsed(panel, collapsed) {
    panel.classList.toggle('mtd-collapsed', collapsed);
    set(COLLAPSE_KEY, collapsed ? 'yes' : 'no');
    renderTitle(panel);
    clampIntoView(panel);   // expanding can push the body past the bottom edge
  }

  function renderTitle(panel) {
    var meta = screenMeta() || {};
    var t = panel.querySelector('.mtd-titletext');
    if (panel.classList.contains('mtd-collapsed')) {
      t.innerHTML = '<span class="mtd-chip">' + esc(meta.name) + '</span>' +
                    '<span style="color:#8b93a1"> · ' + esc(meta.access) + '</span>';
      t.style.textTransform = 'none';
      t.style.letterSpacing = '0';
    } else {
      t.textContent = 'debug · ' + COMBO_LABEL + ' to close';
      t.style.textTransform = 'uppercase';
      t.style.letterSpacing = '.09em';
    }
  }

  function renderScreen(panel, meta) {
    meta = meta || {};
    panel.querySelector('.mtd-name').textContent = meta.name || '—';
    panel.querySelector('.mtd-path').textContent = meta.path || '';

    panel.querySelector('.mtd-screen').innerHTML =
      row('endpoint', meta.endpoint) +
      row('kind', meta.kind) +
      row('template', meta.template);

    var colour = meta.access_colour || '#999999';
    panel.querySelector('.mtd-access').innerHTML =
      '<div><span class="mtd-pill" style="background:' + colour + '">' +
        esc(meta.access_label || meta.access) + '</span></div>' +
      '<div class="mtd-note">' + esc(meta.access_description) + '</div>' +
      (meta.condition ? '<div class="mtd-note">' + esc(meta.condition) + '</div>' : '');

    renderTitle(panel);
  }

  function row(k, v) {
    return '<div class="mtd-row"><span class="mtd-k">' + k +
           '</span><span class="mtd-v">' + esc(v) + '</span></div>';
  }

  var inflight = null;
  function fetchViewer(panel, meta) {
    meta = meta || {};
    var url = '/debug/state?endpoint=' + encodeURIComponent(meta.endpoint || '') +
              '&section_id=' + encodeURIComponent(meta.section_id || '');
    if (inflight) inflight.abort();
    inflight = new AbortController();
    fetch(url, { signal: inflight.signal, credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (v) {
        var box = panel.querySelector('.mtd-viewer');
        if (!box) return;
        var html =
          '<div class="mtd-row"><span class="mtd-k">logged in</span>' +
            '<span class="mtd-v">' + yesno(v.authenticated) + '</span></div>' +
          row('identity', v.identity) +
          row('role', v.role) +
          (v.perspective ? row('viewing as', v.perspective + '  (real: ' + v.real_role + ')') : '') +
          row('schools', (v.schools || []).join(', ') || 'none');
        if (v.section_context) {
          var c = v.section_context;
          html += row('section', c.name + ' #' + c.id) +
            '<div class="mtd-row"><span class="mtd-k">&nbsp;member</span>' +
              '<span class="mtd-v">' + yesno(c.is_member) + '</span></div>' +
            '<div class="mtd-row"><span class="mtd-k">&nbsp;owner</span>' +
              '<span class="mtd-v">' + yesno(c.is_owner_teacher) + '</span></div>';
        }
        html += '<div class="mtd-note">' + esc(v.verdict) + '</div>';
        box.innerHTML = html;
        // The panel only reaches its final height now, so re-clamp: the build-
        // time clamp measured a panel with this section still empty.
        clampIntoView(panel);
      })
      .catch(function () { /* aborted or offline — leave the last render */ });
  }

  // ── Pop-out window (optional, for a second monitor) ──────────────────────
  function openPopout() {
    var url = document.body.getAttribute('data-debug-url') || '/debug/panel';
    var win = window.open(url, WINDOW_NAME, 'popup=yes,width=480,height=560,left=40,top=40');
    if (win) {
      try { win.focus(); } catch (e) { /* browsers may ignore this */ }
    } else {
      alert('The popup was blocked. Allow popups for this site, or open ' + url +
            ' in a tab — it follows along as you navigate.');
    }
  }

  // ── Toggle ───────────────────────────────────────────────────────────────
  function toggle() {
    var next = !isOn();
    set(STORAGE_KEY, next ? 'on' : 'off');
    publishScreen();
    if (next) buildPanel(screenMeta());
    else removePanel();
  }

  document.addEventListener('keydown', function (e) {
    if (!MATCHES_TOGGLE(e)) return;
    e.preventDefault();
    toggle();
  });

  function init() {
    if (isOn()) buildPanel(screenMeta());
  }

  publishScreen();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Keep in sync when toggled from another tab.
  window.addEventListener('storage', function (e) {
    if (e.key !== STORAGE_KEY) return;
    if (isOn()) { if (!document.getElementById(PANEL_ID)) buildPanel(screenMeta()); }
    else removePanel();
  });

  window.MusicianshipDebug = {
    toggle: toggle, isOn: isOn, combo: COMBO_LABEL, popOut: openPopout
  };
})();
