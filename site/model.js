(function (root, factory) {
  if (typeof module === 'object' && module.exports) { module.exports = factory(); }
  else { root.MAModel = factory(); }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // The committee baseline: the repo's decision-page defaults. The "repo
  // baseline" preset restores exactly these.
  var DEFAULTS = {
    deal: 0,            // first deal in the book (Amazon -> Whole Foods)
    sector: 'e-commerce',
    multiple: 8.0,      // entry EV/EBITDA, the committee's screen input
    capture: 0.5,       // contracted synergy capture
    wacc: 0.08,         // discount rate
    leverage: 4.0,      // LBO-lite leverage, x EBITDA
    scenEntry: 6.0,     // IRR scenario gates (the expansion case)
    scenExit: 12.0,
    hold: 5,
    cagr: 0.05          // e-commerce sector EBITDA CAGR
  };

  // ------------------------------------------------------------------
  // the 12-deal book (mirror data/deals.py; valueB is display-only -
  // every computation here is scale-invariant, the IRR proof carries it)
  // ------------------------------------------------------------------
  var DEALS = [
    { acquirer: 'Amazon', target: 'Whole Foods Market', year: 2017, valueB: 13.7, sector: 'e-commerce' },
    { acquirer: 'Walmart', target: 'Flipkart', year: 2018, valueB: 16.0, sector: 'e-commerce' },
    { acquirer: 'Walmart', target: 'Jet.com', year: 2016, valueB: 3.4, sector: 'e-commerce' },
    { acquirer: 'Amazon', target: 'Souq', year: 2017, valueB: 0.58, sector: 'e-commerce' },
    { acquirer: 'Alibaba', target: 'Ele.me', year: 2018, valueB: 9.5, sector: 'e-commerce' },
    { acquirer: 'Alibaba', target: 'Laila (LaLalife)', year: 2019, valueB: 1.45, sector: 'e-commerce' },
    { acquirer: 'Uber', target: 'Postmates', year: 2020, valueB: 2.65, sector: 'logistics' },
    { acquirer: 'XPO Logistics', target: 'New England Logistics (UPS)', year: 2021, valueB: 8.4, sector: 'logistics' },
    { acquirer: 'Amazon', target: 'iRobot', year: 2024, valueB: 1.5, sector: 'logistics' },
    { acquirer: 'Kuehne+Nagel', target: 'Hermes', year: 2018, valueB: 2.3, sector: 'logistics' },
    { acquirer: 'JD.com', target: 'Debon Express', year: 2015, valueB: 0.33, sector: 'logistics' },
    { acquirer: 'UPS', target: 'MPS Group', year: 2020, valueB: 2.1, sector: 'logistics' }
  ];

  // Sector constants (mirror decision/defaults; tagged [unverified] in the
  // repo - committee inputs, not sourced figures).
  var SECTOR = {
    'e-commerce': { capex: 90.0, floor: 0.40, cagr: 0.05, label: 'e-commerce' },
    'logistics':  { capex: 160.0, floor: 0.50, cagr: 0.03, label: 'logistics' }
  };

  // 100-unit base constants (mirror model/accretive.py and decision_page.py).
  var TARGET_EBITDA = 10.0;
  var ANNUAL_SYNERGY = 2.0;          // stated run-rate, 20% of target EBITDA
  var ACQ_NI = 100.0;                // acquirer base net income
  var NI_PER_EBITDA = 0.30;          // target NI conversion
  var DEBT_SHARE = 0.60;             // debt-funded share of the EV
  var DEBT_RATE = 0.05;              // after-tax financing rate
  var BUILD_VALUE_PARITY = 0.85;
  var BUILD_CAPTURE_HAIRCUT = 0.60;
  var PARTNER_VALUE_SHARE = 0.70;
  var PARTNER_RATE_CARD = 25.0;      // per year, target-EBITDA units
  var HOLD_YEARS = 5;

  // DCF shape (mirror model/sensitivity.py defaults).
  var BASE_FCF = 100.0;
  var FCF_CAGR = 0.05;
  var TERMINAL_GROWTH = 0.025;
  var DCF_EBITDA = 100.0;            // implied-multiple denominator

  // ------------------------------------------------------------------
  // the value anchor: target DCF (mirror sensitivity.dcf_value)
  // ------------------------------------------------------------------
  function dcfValue(wacc, years) {
    years = years == null ? 5 : years;
    if (wacc <= 0 || wacc <= TERMINAL_GROWTH) { return NaN; }
    var pv = 0;
    var last = 0;
    for (var t = 1; t <= years; t++) {
      var cf = BASE_FCF * Math.pow(1 + FCF_CAGR, t - 1);
      pv += cf / Math.pow(1 + wacc, t);
      last = cf;
    }
    var tv = last * (1 + TERMINAL_GROWTH) / (wacc - TERMINAL_GROWTH);
    pv += tv / Math.pow(1 + wacc, years);
    return pv;
  }

  // intrinsic EV/EBITDA at a WACC (~31x at 6%, ~19.8x at 8%, ~11x at 12%)
  function intrWacc(wacc, years) {
    return dcfValue(wacc, years) / DCF_EBITDA;
  }

  function intrinsicValue(wacc, years) {
    return intrWacc(wacc, years) * TARGET_EBITDA;
  }

  // ------------------------------------------------------------------
  // the trigger line: accretion zero-line m*(c) (mirror surfaces._m_star)
  // ------------------------------------------------------------------
  // m*(c) = (ni + S*c/E) / (ds * rate)  -  closed form, year-1 accretion
  // set to zero, linear in the entry multiple.
  function mStar(capture) {
    var conv = NI_PER_EBITDA + ANNUAL_SYNERGY * capture / TARGET_EBITDA;
    return conv / (DEBT_SHARE * DEBT_RATE);
  }

  function zeroLine() {
    return [0.0, 0.25, 0.5, 0.75, 1.0].map(function (c) { return mStar(c); });
  }

  // year-1 EPS accretion at a multiple and scalar capture (mirror
  // model.accretive.accretion)
  function accretion(multiple, capture) {
    var ev = TARGET_EBITDA * multiple;
    var fin = ev * DEBT_SHARE * DEBT_RATE;
    var tni = TARGET_EBITDA * NI_PER_EBITDA + ANNUAL_SYNERGY * capture;
    return (ACQ_NI + tni - fin) / ACQ_NI - 1.0;
  }

  // buy-zone at a price: accretive AND below the wacc-implied intrinsic
  // value (mirror surfaces.buy_zone)
  function buyZone(multiple, capture, wacc) {
    return accretion(multiple, capture) > 0.0 &&
           multiple < intrWacc(wacc, HOLD_YEARS);
  }

  // the single number a mandate quotes (mirror surfaces.deal_trigger)
  function dealTrigger(multiple, wacc) {
    var caps = [0.0, 0.25, 0.5, 0.75, 1.0];
    var inZone = caps.filter(function (c) { return buyZone(multiple, c, wacc); });
    return {
      multiple: multiple,
      wacc: wacc,
      intrinsic: intrWacc(wacc, HOLD_YEARS),
      inZoneCaptures: inZone,
      minCaptureInZone: inZone.length ? inZone[0] : null
    };
  }

  // ------------------------------------------------------------------
  // synergy decay (mirror decision/synergy_decay.py)
  // ------------------------------------------------------------------
  function captureProfile(years, floor, schedule) {
    years = years || HOLD_YEARS;
    schedule = schedule || 'linear';
    var prof = {};
    for (var t = 1; t <= years; t++) {
      if (t === 1) { prof[t] = 1.0; }
      else if (schedule === 'linear') {
        var frac = (t - 1) / (years - 1);
        prof[t] = 1.0 - (1.0 - floor) * frac;
      } else { // step
        prof[t] = (t <= Math.floor(years / 2)) ? 1.0 : floor;
      }
    }
    return prof;
  }

  // realized-synergy fraction stream -> per-year EPS accretion
  function yearlyAccretions(multiple, floor, years) {
    years = years || HOLD_YEARS;
    var prof = captureProfile(years, floor, 'linear');
    var out = [];
    for (var t = 1; t <= years; t++) { out.push(accretion(multiple, prof[t])); }
    return out;
  }

  // "accretive for N years, then inverts"
  function accretiveYears(multiple, floor, years) {
    var series = yearlyAccretions(multiple, floor, years);
    var n = 0;
    for (var i = 0; i < series.length; i++) {
      if (series[i] <= 0.0) { break; }
      n++;
    }
    return n;
  }

  // PV of the decaying synergy stream (mirror cumulative_synergy_value)
  function cumSynergyValue(annual, years, floor, wacc) {
    var prof = captureProfile(years, floor, 'linear');
    var pv = 0;
    for (var t = 1; t <= years; t++) {
      pv += annual * prof[t] / Math.pow(1 + wacc, t);
    }
    return pv;
  }

  // level-annuity PV factor (mirror surfaces._annuity_pv)
  function annuityPV(wacc, years) {
    if (wacc <= 0) { return years; }
    return (1.0 - Math.pow(1.0 + wacc, -years)) / wacc;
  }

  // ------------------------------------------------------------------
  // the decision page: buy / build / partner on one yardstick
  // (mirror decision/decision_page.py)
  // ------------------------------------------------------------------
  function strategyEconomics(sector, buyPriceMultiple, buyCapture, wacc, years) {
    var sc = SECTOR[sector];
    years = years || HOLD_YEARS;
    var V = intrinsicValue(wacc, years);
    var price = buyPriceMultiple * TARGET_EBITDA;
    var syBuy = cumSynergyValue(ANNUAL_SYNERGY * buyCapture, years, sc.floor, wacc);
    var syBuild = cumSynergyValue(ANNUAL_SYNERGY * buyCapture * BUILD_CAPTURE_HAIRCUT,
                                  years, sc.floor, wacc);
    var partnerCostPV = PARTNER_RATE_CARD * annuityPV(wacc, years);
    var capex = sc.capex;

    return {
      V: V,
      price: price,
      synBuy: syBuy,
      partnerCostPV: partnerCostPV,
      capex: capex,
      strategies: {
        buy:     { net: V + syBuy - price },
        build:   { net: V * BUILD_VALUE_PARITY + syBuild - capex },
        partner: { net: V * PARTNER_VALUE_SHARE - partnerCostPV },
        none:    { net: 0.0 }
      }
    };
  }

  // the buy price cap: highest entry multiple where buy still nets >= the
  // best alternative (mirror buy_price_cap)
  function buyPriceCap(sector, buyCapture, wacc, years) {
    var grid = [];
    for (var i = 0; i <= 64; i++) { grid.push(4.0 + i * 0.25); } // 4.0..20.0
    var winners = [];
    grid.forEach(function (p) {
      var s = strategyEconomics(sector, p, buyCapture, wacc, years).strategies;
      if (s.buy.net >= Math.max(s.build.net, s.partner.net, 0.0)) { winners.push(p); }
    });
    var cap = winners.length ? Math.max.apply(null, winners) : 0.0;
    var at = strategyEconomics(sector, cap > 0 ? cap : 4.0, buyCapture, wacc, years).strategies;
    var alt = at.build.net >= at.partner.net ? 'build' : 'partner';
    return {
      cap: cap,
      alternative: alt,
      altPV: at[alt].net,
      buyPVAtCap: at.buy.net
    };
  }

  // one recommendation + trigger line (mirror recommend)
  function recommend(sector, buyPriceMultiple, buyCapture, wacc, years) {
    var eco = strategyEconomics(sector, buyPriceMultiple, buyCapture, wacc, years);
    var s = eco.strategies;
    var winner = 'buy';
    ['build', 'partner', 'none'].forEach(function (k) {
      if (s[k].net > s[winner].net) { winner = k; }
    });
    var capInfo = buyPriceCap(sector, buyCapture, wacc, years);
    var dt = dealTrigger(buyPriceMultiple, wacc);
    var trigger;
    if (winner === 'buy') {
      trigger = 'BUY at <= ' + capInfo.cap.toFixed(1) + 'x with >= ' +
                (buyCapture * 100).toFixed(0) + '% capture; above that, ' +
                capInfo.alternative + ' is cheaper';
    } else {
      trigger = 'at ' + buyPriceMultiple.toFixed(0) + 'x, ' + winner +
                ' is cheaper than buy; buy only at <= ' +
                capInfo.cap.toFixed(1) + 'x';
    }
    var floor = SECTOR[sector].floor;
    return {
      sector: sector,
      winner: winner.toUpperCase(),
      trigger: trigger,
      cap: capInfo.cap,
      capAlternative: capInfo.alternative,
      minCaptureInZone: dt.minCaptureInZone,
      net: s,
      accYears: accretiveYears(buyPriceMultiple, floor, years),
      decaySeries: yearlyAccretions(buyPriceMultiple, floor, years),
      intrinsic: intrWacc(wacc, years),
      V: eco.V,
      synBuy: eco.synBuy,
      partnerCostPV: eco.partnerCostPV,
      capex: eco.capex
    };
  }

  // one row per deal in the book (mirror page)
  function page(buyPriceMultiple, buyCapture, wacc, years) {
    return DEALS.map(function (d, i) {
      var r = recommend(d.sector, buyPriceMultiple, buyCapture, wacc, years);
      var net = r.net;
      return {
        i: i,
        deal: d.acquirer + ' -> ' + d.target + ' (' + d.year + ')',
        sector: d.sector,
        valueB: d.valueB,
        recommendation: r.winner,
        cap: r.cap,
        alternative: r.capAlternative,
        minCaptureInZone: r.minCaptureInZone,
        pvBuy: net.buy.net,
        pvBuild: net.build.net,
        pvPartner: net.partner.net,
        trigger: r.trigger
      };
    });
  }

  // ------------------------------------------------------------------
  // IRR waterfalls (mirror decision/irr_waterfall.py)
  // ------------------------------------------------------------------
  var IRR_SCENARIOS = [
    { entry: 6.0,  exit: 12.0, label: '6x in -> 12x out (expansion)' },
    { entry: 8.0,  exit: 8.0,  label: '8x in -> 8x out (growth only)' },
    { entry: 12.0, exit: 6.0,  label: '12x in -> 6x out (mean-reversion)' }
  ];

  // the gate-by-gate equity bridge; implied IRR = MOC^(1/H) - 1
  function equityBridge(scen, sector, leverage, holdYears, ebitdaEntry, cagrOverride) {
    leverage = leverage == null ? 4.0 : leverage;
    holdYears = holdYears || HOLD_YEARS;
    ebitdaEntry = ebitdaEntry == null ? 100.0 : ebitdaEntry;
    var cagr = cagrOverride != null ? cagrOverride : SECTOR[sector].cagr;
    var growth = Math.pow(1.0 + cagr, holdYears);
    var entryEq = ebitdaEntry * (scen.entry - leverage);
    var gGrow = ebitdaEntry * (growth - 1.0) * scen.entry;
    var gExp = ebitdaEntry * growth * (scen.exit - scen.entry);
    var exitEq = entryEq + gGrow + gExp;
    var moc = exitEq / entryEq;
    var impliedIrr = Math.pow(moc, 1.0 / holdYears) - 1.0;
    return {
      entryEq: entryEq / ebitdaEntry,
      gGrow: gGrow / ebitdaEntry,
      gExp: gExp / ebitdaEntry,
      exitEq: exitEq / ebitdaEntry,
      moc: moc,
      impliedIrr: impliedIrr,
      growthShare: (gGrow + gExp) ? gGrow / (gGrow + gExp) : 0.0
    };
  }

  // the three committee scenarios for a sector (mirror per_deal_irr_matrix)
  function irrScenarios(sector, leverage, holdYears, ebitdaEntry) {
    return IRR_SCENARIOS.map(function (sc) {
      var b = equityBridge(sc, sector, leverage, holdYears, ebitdaEntry);
      return {
        label: sc.label,
        entry: sc.entry,
        exit: sc.exit,
        moc: b.moc,
        irr: b.impliedIrr,
        growthShare: b.growthShare,
        entryEq: b.entryEq,
        gGrow: b.gGrow,
        gExp: b.gExp
      };
    });
  }

  // ------------------------------------------------------------------
  // rounding the page reports in (Python round(x, n) semantics on the
  // nearest double; these are the pins' own reference values)
  // ------------------------------------------------------------------
  function roundTo(x, n) {
    var f = Math.pow(10, n);
    return Math.round(x * f) / f;
  }

  return {
    DEFAULTS: DEFAULTS,
    DEALS: DEALS,
    SECTOR: SECTOR,
    HOLD_YEARS: HOLD_YEARS,
    IRR_SCENARIOS: IRR_SCENARIOS,
    dcfValue: dcfValue,
    intrWacc: intrWacc,
    intrinsicValue: intrinsicValue,
    mStar: mStar,
    zeroLine: zeroLine,
    accretion: accretion,
    buyZone: buyZone,
    dealTrigger: dealTrigger,
    captureProfile: captureProfile,
    yearlyAccretions: yearlyAccretions,
    accretiveYears: accretiveYears,
    cumSynergyValue: cumSynergyValue,
    annuityPV: annuityPV,
    strategyEconomics: strategyEconomics,
    buyPriceCap: buyPriceCap,
    recommend: recommend,
    page: page,
    equityBridge: equityBridge,
    irrScenarios: irrScenarios,
    roundTo: roundTo
  };
}));
