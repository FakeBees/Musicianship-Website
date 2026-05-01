(function () {
  'use strict';

  var BASE = 'https://nbrosowsky.github.io/tonejs-instruments/samples/';

  // Wraps an instrument with a compressor to even out dynamics across the range.
  // Returns a proxy exposing triggerAttackRelease and dispose so callers need not branch.
  function compressed(inst, threshold, ratio) {
    var comp = new Tone.Compressor({
      threshold: threshold || -24,
      ratio:     ratio     || 8,
      attack:    0.004,
      release:   0.25,
      knee:      8,
    }).toDestination();
    inst.connect(comp);
    return {
      triggerAttackRelease: function (note, dur) { inst.triggerAttackRelease(note, dur); },
      triggerAttack:        function (note)       { inst.triggerAttack(note); },
      triggerRelease:       function (note)       { inst.triggerRelease(note); },
      dispose: function () { inst.dispose(); comp.dispose(); },
    };
  }

  var DEFS = [
    {
      id: 'salamander',
      label: 'Salamander Grand Piano',
      create: function () {
        return new Tone.Sampler({
          urls: {
            A0:'A0.mp3',  C1:'C1.mp3',  'F#1':'Fs1.mp3', A1:'A1.mp3',
            C2:'C2.mp3',  'F#2':'Fs2.mp3', A2:'A2.mp3',  C3:'C3.mp3',
            'F#3':'Fs3.mp3', A3:'A3.mp3', C4:'C4.mp3',   'F#4':'Fs4.mp3',
            A4:'A4.mp3',  C5:'C5.mp3',  'F#5':'Fs5.mp3', A5:'A5.mp3',
            C6:'C6.mp3',  'F#6':'Fs6.mp3', A6:'A6.mp3',  C7:'C7.mp3',
            'F#7':'Fs7.mp3', A7:'A7.mp3', C8:'C8.mp3',
          },
          release: 2,
          baseUrl: 'https://tonejs.github.io/audio/salamander/',
        }).toDestination();
      },
    },
    {
      id: 'synth',
      label: 'Synthesizer',
      create: function () {
        var synth = new Tone.PolySynth(Tone.Synth, {
          oscillator: { type: 'triangle' },
          envelope: { attack: 0.01, release: 0.8 },
        });
        return compressed(synth, -20, 10);
      },
    },
    {
      id: 'organ',
      label: 'Organ',
      create: function () {
        var sampler = new Tone.Sampler({
          urls: {
            C1:'C1.mp3', 'D#1':'Ds1.mp3', 'F#1':'Fs1.mp3', A1:'A1.mp3',
            C2:'C2.mp3', 'D#2':'Ds2.mp3', 'F#2':'Fs2.mp3', A2:'A2.mp3',
            C3:'C3.mp3', 'D#3':'Ds3.mp3', 'F#3':'Fs3.mp3', A3:'A3.mp3',
            C4:'C4.mp3', 'D#4':'Ds4.mp3', 'F#4':'Fs4.mp3', A4:'A4.mp3',
            C5:'C5.mp3', 'D#5':'Ds5.mp3', 'F#5':'Fs5.mp3', A5:'A5.mp3',
            C6:'C6.mp3',
          },
          release: 0.5,
          baseUrl: BASE + 'organ/',
        });
        return compressed(sampler, -22, 8);
      },
    },
    {
      id: 'flute',
      label: 'Flute',
      create: function () {
        var sampler = new Tone.Sampler({
          urls: {
            A4:'A4.mp3', A5:'A5.mp3', A6:'A6.mp3',
            C4:'C4.mp3', C5:'C5.mp3', C6:'C6.mp3', C7:'C7.mp3',
            E4:'E4.mp3', E5:'E5.mp3', E6:'E6.mp3',
          },
          release: 1,
          baseUrl: BASE + 'flute/',
        });
        return compressed(sampler, -26, 6);
      },
    },
    {
      id: 'guitar',
      label: 'Guitar (acoustic)',
      create: function () {
        return new Tone.Sampler({
          urls: {
            C3:'C3.mp3', 'C#3':'Cs3.mp3', D2:'D2.mp3', D3:'D3.mp3', D4:'D4.mp3',
            'D#2':'Ds2.mp3', 'D#3':'Ds3.mp3',
            E2:'E2.mp3', E3:'E3.mp3', E4:'E4.mp3',
            F2:'F2.mp3', F3:'F3.mp3', F4:'F4.mp3',
            'F#2':'Fs2.mp3', 'F#3':'Fs3.mp3', 'F#4':'Fs4.mp3',
            G2:'G2.mp3', G3:'G3.mp3', G4:'G4.mp3',
            'G#2':'Gs2.mp3', 'G#3':'Gs3.mp3', 'G#4':'Gs4.mp3',
            A2:'A2.mp3', A3:'A3.mp3', A4:'A4.mp3',
            'A#2':'As2.mp3', 'A#3':'As3.mp3', 'A#4':'As4.mp3',
            B2:'B2.mp3', B3:'B3.mp3', B4:'B4.mp3',
            C4:'C4.mp3', 'C#4':'Cs4.mp3', C5:'C5.mp3', 'C#5':'Cs5.mp3',
          },
          release: 1.5,
          baseUrl: BASE + 'guitar-acoustic/',
        }).toDestination();
      },
    },
    {
      id: 'marimba',
      label: 'Marimba',
      create: function () {
        return new Tone.Sampler({
          urls: {
            C5:'C5.mp3', C6:'C6.mp3', C7:'C7.mp3', C8:'C8.mp3',
            G4:'G4.mp3', G5:'G5.mp3', G6:'G6.mp3', G7:'G7.mp3',
          },
          release: 1,
          baseUrl: BASE + 'xylophone/',
        }).toDestination();
      },
    },
  ];

  window.Instruments = {
    list: DEFS.map(function (d) { return { id: d.id, label: d.label }; }),
    create: function (id) {
      var def = DEFS.find(function (d) { return d.id === id; });
      if (!def) def = DEFS[0];
      return def.create();
    },
  };
})();
