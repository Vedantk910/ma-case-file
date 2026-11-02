#!/usr/bin/env node
'use strict';
// Cross-language pin: the JS model in site/model.js must reproduce the
// Python decision tool's baseline numbers, to the bit. Run `node
// site/verify.js`.
//
// Reference values are the repo's out/decision_numbers.json (the Python
// pin file, written by notebooks/run_notebook.py), hard-coded here so the
// harness runs on any clean clone with no generated artifacts. The pin
// file stores each figure at a fixed precision; the JS side is rounded to
// that same precision and compared exactly.
const assert = require('assert');
const M = require('./model.js');

// reference values: out/decision_numbers.json, at the file's own precision
const ref = {
  zero_line: { '0%': 10.0, '25%': 11.6667, '50%': 13.3333, '75%': 15.0, '100%': 16.6667 },
  intrinsic_8: 19.7965,           // intrinsic multiple at the 8% committee rate
  // decision page: e-commerce (rows 0-5) and logistics (rows 6-11)
  page: [
    { cap: 12.0, alt: 'build',   pvBuy: 120.85, pvBuild: 80.0,  pvPar: 38.76, rec: 'BUY' },
    { cap: 12.0, alt: 'build',   pvBuy: 120.85, pvBuild: 80.0,  pvPar: 38.76, rec: 'BUY' },
    { cap: 12.0, alt: 'build',   pvBuy: 120.85, pvBuild: 80.0,  pvPar: 38.76, rec: 'BUY' },
    { cap: 12.0, alt: 'build',   pvBuy: 120.85, pvBuild: 80.0,  pvPar: 38.76, rec: 'BUY' },
    { cap: 12.0, alt: 'build',   pvBuy: 120.85, pvBuild: 80.0,  pvPar: 38.76, rec: 'BUY' },
    { cap: 12.0, alt: 'build',   pvBuy: 120.85, pvBuild: 80.0,  pvPar: 38.76, rec: 'BUY' },
    { cap: 16.0, alt: 'partner', pvBuy: 121.04, pvBuild: 10.11, pvPar: 38.76, rec: 'BUY' },
    { cap: 16.0, alt: 'partner', pvBuy: 121.04, pvBuild: 10.11, pvPar: 38.76, rec: 'BUY' },
    { cap: 16.0, alt: 'partner', pvBuy: 121.04, pvBuild: 10.11, pvPar: 38.76, rec: 'BUY' },
    { cap: 16.0, alt: 'partner', pvBuy: 121.04, pvBuild: 10.11, pvPar: 38.76, rec: 'BUY' },
    { cap: 16.0, alt: 'partner', pvBuy: 121.04, pvBuild: 10.11, pvPar: 38.76, rec: 'BUY' },
    { cap: 16.0, alt: 'partner', pvBuy: 121.04, pvBuild: 10.11, pvPar: 38.76, rec: 'BUY' }
  ],
  // IRR waterfall, sector x scenario (expansion / growth-only / mean-reversion)
  irr: {
    'e-commerce': [
      { irr: 41.4, moc: 5.66, grow: 0.18 },
      { irr: 9.2,  moc: 1.55, grow: 1.0 },
      { irr: -14.5, moc: 0.46, grow: -0.76 }
    ],
    'logistics': [
      { irr: 37.7, moc: 4.96, grow: 0.12 },
      { irr: 5.7,  moc: 1.32, grow: 1.0 },
      { irr: -18.1, moc: 0.37, grow: -0.38 }
    ]
  },
  // decay table, full-capture schedule (0.5 floor), the pin file's own cells
  decayY1_6x: 0.032, decayY5_12x: 0.004
};

// round the JS value to the pin file's precision, then compare exactly
function pin(label, got, want) {
  assert.strictEqual(got, want, label + ': got ' + got + ', want ' + want);
  console.log('ok  ' + label + ' = ' + got);
}

// --- zero-line m*(c), closed form (pinned in the test suite to 1e-9) ---
const zl = M.zeroLine();
const capKeys = ['0%', '25%', '50%', '75%', '100%'];
zl.forEach((v, i) => pin('m*(' + capKeys[i] + ') @4dp', M.roundTo(v, 4), ref.zero_line[capKeys[i]]));
console.log('ok  zero-line: ' + capKeys.map(k => ref.zero_line[k] + 'x').join(' / '));

// --- intrinsic anchor: the 8% WACC-implied DCF multiple ---
pin('intrinsic multiple @8% @4dp', M.roundTo(M.intrWacc(0.08), 4), ref.intrinsic_8);

// --- the decision page: recommendation, cap, alternative and net PVs ---
const rows = M.page(8.0, 0.5, 0.08, 5);
rows.forEach((r, i) => {
  const w = ref.page[i];
  pin('deal ' + i + ' rec', r.recommendation, w.rec);
  pin('deal ' + i + ' cap', r.cap, w.cap);
  pin('deal ' + i + ' alt', r.alternative, w.alt);
  pin('deal ' + i + ' PV buy @2dp', M.roundTo(r.pvBuy, 2), w.pvBuy);
  pin('deal ' + i + ' PV build @2dp', M.roundTo(r.pvBuild, 2), w.pvBuild);
  pin('deal ' + i + ' PV partner @2dp', M.roundTo(r.pvPartner, 2), w.pvPar);
});
console.log('ok  decision page: ' + rows.length +
  ' deals, rec / cap / alternative / net PVs match the Python baseline');

// --- IRR waterfalls: implied IRR, MOC and the growth-share gate split ---
Object.keys(ref.irr).forEach(function (sector) {
  M.irrScenarios(sector, 4.0, 5, 100.0).forEach(function (sc, k) {
    const w = ref.irr[sector][k];
    pin(sector + ' IRR ' + k + ' @1dp', M.roundTo(sc.irr * 100, 1), w.irr);
    pin(sector + ' MOC ' + k + ' @2dp', M.roundTo(sc.moc, 2), w.moc);
    pin(sector + ' growth share ' + k + ' @2dp', M.roundTo(sc.growthShare, 2), w.grow);
  });
});
console.log('ok  IRR waterfalls: IRR / MOC / gate split match the Python baseline');

// --- the decay signature: "accretive for N years, then inverts" ---
assert.strictEqual(M.accretiveYears(8.0, M.SECTOR['e-commerce'].floor, 5), 5);
assert.strictEqual(M.accretiveYears(14.0, M.SECTOR['e-commerce'].floor, 5), 3);
assert.strictEqual(M.accretiveYears(18.0, M.SECTOR['e-commerce'].floor, 5), 0);
console.log('ok  decay signature: 5 yrs @8x, 3 @14x, 0 @18x (e-com floor)');

// the Y1/Y5 cells of the pin file's decay table (0.5 floor, default
// schedule), compared bit-for-bit - no rounding needed
pin('Y1 @6x decay table', M.yearlyAccretions(6.0, 0.5, 5)[0], 0.03200000000000003);
pin('Y5 @12x decay table', M.yearlyAccretions(12.0, 0.5, 5)[4], 0.0040000000000000036);
pin('accretive years @12x (0.5 floor)', M.accretiveYears(12.0, 0.5, 5), 5);
console.log('ok  decay-table cells match the Python baseline');

console.log('\nAll JS pins match the Python decision tool.');
