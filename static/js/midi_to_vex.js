(function () {
  'use strict';

  var FLAT_KEYS = ['F', 'Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Dm', 'Gm', 'Cm', 'Fm'];

  // pitch class index → [natural letter, sharp spelling, flat spelling]
  var PC_MAP = [
    ['c',  'c',   'c'  ],  // 0  C
    [null, 'c#',  'db' ],  // 1  C#/Db
    ['d',  'd',   'd'  ],  // 2  D
    [null, 'd#',  'eb' ],  // 3  D#/Eb
    ['e',  'e',   'e'  ],  // 4  E
    ['f',  'f',   'f'  ],  // 5  F
    [null, 'f#',  'gb' ],  // 6  F#/Gb
    ['g',  'g',   'g'  ],  // 7  G
    [null, 'g#',  'ab' ],  // 8  G#/Ab
    ['a',  'a',   'a'  ],  // 9  A
    [null, 'a#',  'bb' ],  // 10 A#/Bb
    ['b',  'b',   'b'  ],  // 11 B
  ];

  function midiToVexKey(midiNumber, keySignature) {
    if (midiNumber == null || midiNumber < 0 || midiNumber > 127) return null;
    var octave = Math.floor(midiNumber / 12) - 1;
    var pc     = midiNumber % 12;
    var entry  = PC_MAP[pc];
    var useFlatSpelling = FLAT_KEYS.indexOf(keySignature) !== -1;
    var letter = useFlatSpelling ? entry[2] : entry[1];
    return letter + '/' + octave;
  }

  window.midiToVexKey = midiToVexKey;
})();
