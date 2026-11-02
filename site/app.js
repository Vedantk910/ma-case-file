(function () {
  'use strict';
  var M = window.MAModel;
  var $ = function (id) { return document.getElementById(id); };

  // slider input -> state key, with its formatter
  var SLIDERS = [
    ['inM', 'multiple', function (v) { return (+v).toFixed(1) + 'x'; }],
    ['inCap', 'capture', function (v) { return (+v) + '%'; }],
    ['inWacc', 'wacc', function (v) { return (+v).toFixed(1) + '%'; }],
    ['inLev', 'leverage', function (v) { return (+v).toFixed(1) + 'x'; }],
    ['inE', 'scenEntry', function (v) { return (+v).toFixed(0) + 'x'; }],
    ['inX', 'scenExit', function (v) { return (+v).toFixed(0) + 'x'; }],
    ['inHold', 'hold', function (v) { return (+v) + 'y'; }],
    ['inCagr', 'cagr', function (v) { return (+v).toFixed(1) + '%'; }]
  ];
  var state = Object.assign({}, M.DEFAULTS);
  // captures / rates stored as fractions in the model; sliders show whole %
  function readState() {
    state = Object.assign({}, M.DEFAULTS);
    state.deal = +$('inDeal').value;
    state.sector = M.DEALS[state.deal].sector;
    state.multiple = +$('inM').value;
    state.capture = +$('inCap').value / 100;
    state.wacc = +$('inWacc').value / 100;
    state.leverage = +$('inLev').value;
    state.scenEntry = +$('inE').value;
    state.scenExit = +$('inX').value;
    state.hold = +$('inHold').value;
    state.cagr = +$('inCagr').value / 100;
  }
  function pushState() {
    $('inDeal').value = String(state.deal);
    $('inM').value = state.multiple; $('inCap').value = state.capture * 100;
    $('inWacc').value = state.wacc * 100; $('inLev').value = state.leverage;
    $('inE').value = state.scenEntry; $('inX').value = state.scenExit;
    $('inHold').value = state.hold; $('inCagr').value = state.cagr * 100;
  }

  function fmtUnits(x) {
    if (!isFinite(x)) return '—';
    return (x >= 0 ? '+' : '−') + Math.abs(x).toFixed(2);
  }
  function fmtPct(x) { return (x >= 0 ? '+' : '−') + Math.abs(x).toFixed(1) + '%'; }

  // track fill: set --v so the webkit gradient shows progress
  function paintTracks() {
    SLIDERS.forEach(function (s) {
      var el = $(s[0]);
      if (!el) return;
      var pct = (el.value - el.min) / (el.max - el.min) * 100;
      el.style.setProperty('--v', pct + '%');
    });
  }

  function populateDeals() {
    var sel = $('inDeal');
    sel.innerHTML = M.DEALS.map(function (d, i) {
      return '<option value="' + i + '">' + d.acquirer + ' → ' + d.target +
        ' (' + d.year + ') · $' + d.valueB + 'B · ' + d.sector + '</option>';
    }).join('');
  }

  // ------------------------------------------------------------------
  // render: one pass recomputes everything from `state`
  // ------------------------------------------------------------------
  var statusShown = true;
  function render() {
    var r = M.recommend(state.sector, state.multiple, state.capture, state.wacc, state.hold);
    var dz = M.dealTrigger(state.multiple, state.wacc);
    var net = r.net;

    // outputs next to sliders
    SLIDERS.forEach(function (s) {
      var el = $(s[0]);
      if (el && $('o' + s[0].slice(2))) { $('o' + s[0].slice(2)).textContent = s[2](el.value); }
    });
    paintTracks();

    // verdict
    var rec = r.winner;
    var recEl = $('rec');
    recEl.textContent = rec === 'NONE' ? 'DECLINE' : rec;
    recEl.className = 'tool-verdict rec-' + rec.toLowerCase();
    $('recLine').textContent = (rec === 'NONE'
      ? 'No option creates value at ' + state.multiple.toFixed(1) + 'x — do not do it.'
      : r.trigger);
    // verdict flip dl
    $('dCap').textContent = r.cap.toFixed(1) + 'x';
    $('dAlt').textContent = r.capAlternative;
    $('dAccYrs').textContent = r.accYears + '/5';
    $('pvBuy').textContent = fmtUnits(net.buy.net);
    $('pvBuild').textContent = fmtUnits(net.build.net);
    $('pvPar').textContent = fmtUnits(net.partner.net);
    // hero number: the buy-cap multiple, live
    $('heroCap').textContent = r.cap.toFixed(1);
    $('heroTail').textContent = 'the buy cap at ' + Math.round(state.capture * 100) +
      '% capture. Buy at or below it; above it, ' + r.capAlternative + ' is cheaper.';

    // derivation
    $('dWacc').textContent = (state.wacc * 100).toFixed(1);
    $('dV').textContent = r.V.toFixed(1);
    $('dMStar').textContent = M.mStar(state.capture).toFixed(2) + 'x';
    $('dM').textContent = state.multiple.toFixed(1);
    $('dPvBuy').textContent = fmtUnits(net.buy.net);
    $('dPvBuild').textContent = fmtUnits(net.build.net);
    $('dPvPar').textContent = fmtUnits(net.partner.net);
    $('dCap2').textContent = r.cap.toFixed(1) + 'x';
    $('dAlt2').textContent = r.capAlternative;
    $('dM2').textContent = state.multiple.toFixed(1);
    $('dRec').textContent = rec === 'NONE' ? 'DECLINE' : rec;
    $('dAccYrs2').textContent = r.accYears;
    // min capture in zone (the pure buy-zone bar)
    $('dSector').textContent = state.sector;
    $('dMDecay').textContent = state.multiple.toFixed(1);
    $('dDecayN').textContent = r.accYears;

    // book table
    var rows = M.page(state.multiple, state.capture, state.wacc, state.hold);
    var tb = $('bookTable').querySelector('tbody');
    tb.innerHTML = rows.map(function (row) {
      var cls = row.i === state.deal ? ' class="you"' : '';
      var recCls = row.recommendation === 'NONE' ? 'none' : row.recommendation;
      return '<tr' + cls + ' data-i="' + row.i + '">' +
        '<td>' + row.deal + ' <span class="val">$' + row.valueB + 'B</span>' +
          (row.i === state.deal ? ' <span class="hint">(you)</span>' : '') + '</td>' +
        '<td class="n"><span class="badge b-' + recCls + '">' +
          (row.recommendation === 'NONE' ? 'DECLINE' : row.recommendation) + '</span></td>' +
        '<td class="n">' + row.cap.toFixed(1) + 'x</td>' +
        '<td class="n">' + row.alternative + '</td>' +
        '<td class="n">' + row.pvBuy.toFixed(1) + '</td>' +
        '<td class="n">' + row.pvBuild.toFixed(1) + '</td>' +
        '<td class="n">' + row.pvPartner.toFixed(1) + '</td>' +
        '</tr>';
    }).join('');
    tb.querySelectorAll('tr').forEach(function (tr) {
      tr.addEventListener('click', function () {
        state.deal = +tr.getAttribute('data-i');
        state.sector = M.DEALS[state.deal].sector;
        state.cagr = M.SECTOR[state.sector].cagr;
        pushState(); render();
      });
    });

    // decision surface: capture rows x multiple columns, at your WACC
    var capGrid = [0, 0.25, 0.5, 0.75, 1.0];
    var mGrid = [5, 6, 7, 8, 9, 10, 11, 12];
    var el = $('surface');
    el.innerHTML = '<div class="srows">' +
      '<div class="srow paxis"><span class="corner"></span>' +
      mGrid.map(function (m) { return '<span>' + m + 'x</span>'; }).join('') + '</div>' +
      capGrid.map(function (c) {
        return '<div class="srow"><span class="rlabel">' + Math.round(c * 100) + '%</span>' +
          mGrid.map(function (m) {
            var inZone = M.buyZone(m, c, state.wacc);
            return '<div class="scell ' + (inZone ? 'in' : 'out') + '" data-m="' + m +
              '" data-c="' + c + '" title="' + m + 'x at ' + Math.round(c * 100) +
              '% capture → ' + (inZone ? 'in buy zone' : 'out of zone') +
              ' (m* = ' + M.mStar(c).toFixed(2) + 'x)"></div>';
          }).join('') + '</div>';
      }).join('') + '</div>';
    var youIn = M.buyZone(state.multiple, state.capture, state.wacc);
    $('surfaceNote').textContent = 'Your cell: ' + state.multiple.toFixed(1) + 'x at ' +
      Math.round(state.capture * 100) + '% capture → ' +
      (youIn ? 'in the buy zone.' : 'out of the zone — ' +
        (dz.minCaptureInZone != null ? 'you need ≥ ' + Math.round(dz.minCaptureInZone * 100) +
         '% capture at this rate' : 'no capture on the grid reaches it here') + '.') +
      ' Click any cell to set its multiple and capture.';
    el.querySelectorAll('.scell').forEach(function (d) {
      d.addEventListener('click', function () {
        $('inM').value = d.getAttribute('data-m');
        $('inCap').value = (+d.getAttribute('data-c')) * 100;
        readState(); render();
      });
    });

    // synergy decay signature
    var series = r.decaySeries;
    var maxAbs = Math.max.apply(null, series.map(function (x) { return Math.abs(x); }).concat([0.01]));
    var dEl = $('decay');
    dEl.innerHTML = series.map(function (a, i) {
      var w = Math.abs(a) / maxAbs * 100;
      var pos = a > 0;
      return '<div class="drow">' +
        '<span class="dlab">Y' + (i + 1) + '</span>' +
        '<div class="dbar ' + (pos ? 'pos' : 'neg') + '"><i style="width:' + w + '%"></i></div>' +
        '<span class="dval">' + fmtPct(a * 100) + '</span></div>';
    }).join('');

    // IRR waterfall for your gates
    var scen = { entry: state.scenEntry, exit: state.scenExit, label: '' };
    var b = M.equityBridge(scen, state.sector, state.leverage, state.hold, 100.0, state.cagr);
    var gates = [
      { label: 'Entry equity', v: b.entryEq, cls: 'base' },
      { label: '+ EBITDA growth', v: b.gGrow, cls: b.gGrow >= 0 ? 'add' : 'cut' },
      { label: '+ Multiple re-rating', v: b.gExp, cls: b.gExp >= 0 ? 'add' : 'cut' },
      { label: 'Exit equity', v: b.exitEq, cls: 'exit' }
    ];
    var gMax = Math.max.apply(null, gates.map(function (g) { return Math.abs(g.v); }).concat([1]));
    var irrEl = $('irr');
    irrEl.innerHTML =
      '<div class="irr-head"><span>' + state.scenEntry.toFixed(0) + 'x in → ' +
        state.scenExit.toFixed(0) + 'x out · ' + state.leverage.toFixed(1) + 'x lev · ' +
        state.hold + 'y · ' + (state.cagr * 100).toFixed(1) + '% CAGR</span>' +
        '<span class="irr-chips"><b class="irr-irr">' + fmtPct(b.impliedIrr * 100) +
        '</b><span class="chip2">MOC ' + b.moc.toFixed(2) + 'x</span>' +
        '<span class="chip2">growth ' + Math.round(b.growthShare * 100) + '% of gates</span></span></div>' +
      '<div class="wfall">' + gates.map(function (g) {
        var w = Math.abs(g.v) / gMax * 100;
        return '<div class="wrow ' + g.cls + '"><span class="wlab">' + g.label +
          '</span><div class="wbar"><i style="width:' + w + '%"></i></div>' +
          '<span class="wval">' + g.v.toFixed(2) + '</span></div>';
      }).join('') + '</div>';
    $('irrGShare').textContent = Math.max(0, Math.round(b.growthShare * 100));

    // scenario preset buttons
    $('irScen').innerHTML = M.IRR_SCENARIOS.map(function (sc, i) {
      var on = (sc.entry === state.scenEntry && sc.exit === state.scenExit) ? ' on' : '';
      return '<button type="button" data-i="' + i + '" class="irbtn' + on + '">' +
        sc.entry + '→' + sc.exit + 'x</button>';
    }).join('');

    if (statusShown) { statusShown = false; $('status').hidden = true; }
  }

  // ------------------------------------------------------------------
  SLIDERS.forEach(function (s) {
    $(s[0]).addEventListener('input', function () { readState(); render(); });
  });
  $('inDeal').addEventListener('change', function () {
    state.deal = +$('inDeal').value;
    state.sector = M.DEALS[state.deal].sector;
    state.cagr = M.SECTOR[state.sector].cagr;
    $('inCagr').value = state.cagr * 100;
    readState(); render();
  });
  $('irScen') && $('irScen').addEventListener('click', function (e) {
    var btn = e.target.closest('button.irbtn');
    if (!btn) return;
    var sc = M.IRR_SCENARIOS[+btn.getAttribute('data-i')];
    $('inE').value = sc.entry; $('inX').value = sc.exit;
    readState(); render();
  });
  $('btnBaseline').addEventListener('click', function () {
    state = Object.assign({}, M.DEFAULTS);
    state.cagr = M.SECTOR[state.sector].cagr;
    pushState(); render();
  });
  $('btnRandom').addEventListener('click', function () {
    state.deal = Math.floor(Math.random() * M.DEALS.length);
    state.sector = M.DEALS[state.deal].sector;
    state.multiple = 5 + Math.round(Math.random() * 14) * 0.5;
    state.capture = [0, 0.25, 0.5, 0.75, 1.0][Math.floor(Math.random() * 5)];
    state.wacc = 0.06 + Math.round(Math.random() * 12) * 0.005;
    state.leverage = 4;
    state.scenEntry = 6; state.scenExit = 12; state.hold = 5;
    state.cagr = M.SECTOR[state.sector].cagr;
    pushState(); render();
  });

  // mobile menu
  var menu = $('menu'), links = $('links');
  menu.addEventListener('click', function () {
    var open = links.classList.toggle('open');
    menu.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  links.addEventListener('click', function (e) {
    if (e.target.tagName === 'A') { links.classList.remove('open'); menu.setAttribute('aria-expanded', 'false'); }
  });

  // reveal on entry
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
  }, { threshold: 0.1 });
  document.querySelectorAll('.reveal').forEach(function (el) { io.observe(el); });

  populateDeals();
  state.cagr = M.SECTOR[state.sector].cagr;
  pushState(); render();
})();
