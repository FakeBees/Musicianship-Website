(function () {
  'use strict';

  var _handlers        = [];
  var _noteOffHandlers = [];
  var _statusEl  = null;
  var _connected = false;
  var _deviceName = 'not connected';
  var _currentInput = null;
  var _midiAccess   = null;

  function _updateStatus() {
    if (!_statusEl) return;
    _statusEl.textContent = 'MIDI: ' + _deviceName;
    _statusEl.className   = _connected ? 'midi-connected' : 'midi-disconnected';
  }

  function _onMessage(evt) {
    var data     = evt.data;
    var status   = data[0];
    var note     = data[1];
    var velocity = data[2];
    var isNoteOn  = (status & 0xF0) === 0x90;
    var isNoteOff = (status & 0xF0) === 0x80;

    if (isNoteOn && velocity > 0) {
      for (var i = 0; i < _handlers.length; i++) {
        _handlers[i]({ midi: note, velocity: velocity });
      }
    } else if (isNoteOff || (isNoteOn && velocity === 0)) {
      for (var j = 0; j < _noteOffHandlers.length; j++) {
        _noteOffHandlers[j]({ midi: note, velocity: 0 });
      }
    }
  }

  function _bindInput(input) {
    if (_currentInput) {
      _currentInput.onmidimessage = null;
    }
    _currentInput = input;
    if (input) {
      _connected  = true;
      _deviceName = input.name || 'MIDI device';
      input.onmidimessage = _onMessage;
    } else {
      _connected  = false;
      _deviceName = 'not connected';
    }
    _updateStatus();
  }

  function _pickInput(access) {
    var inputs = Array.from(access.inputs.values());
    _bindInput(inputs.length ? inputs[0] : null);
  }

  function _onStateChange(evt) {
    // Re-scan whenever a device connects or disconnects.
    _pickInput(evt.target);
  }

  function _init() {
    if (!navigator.requestMIDIAccess) {
      // Browser doesn't support Web MIDI — expose no-op API.
      _deviceName = 'unsupported';
      _updateStatus();
      return;
    }
    navigator.requestMIDIAccess({ sysex: false }).then(function (access) {
      _midiAccess = access;
      access.onstatechange = _onStateChange;
      _pickInput(access);
    }).catch(function () {
      _deviceName = 'not connected';
      _updateStatus();
    });
  }

  window.MidiInput = {
    getStatus: function () {
      return { connected: _connected, deviceName: _deviceName };
    },
    attachStatusIndicator: function (el) {
      _statusEl = el;
      _updateStatus();
    },
    onNoteOn: function (handler) {
      _handlers.push(handler);
    },
    onNoteOff: function (handler) {
      _noteOffHandlers.push(handler);
    },
  };

  _init();
})();
