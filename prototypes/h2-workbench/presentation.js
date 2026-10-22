(function(root) {
  'use strict';
  const node = typeof module !== 'undefined' && module.exports;
  const i18n = node ? require('../h0-workbench/i18n.js') : root.FamilyH1I18n;
  const rows = node ? require('./h2-translations.js') : root.FamilyH1Translations;
  const dictionaries = i18n.compile(rows);
  const peers = ['iris', 'soren'], phases = ['initial', 'source-revoked', 'publication-revoked', 'observation-only'];
  const lanes = ['observations', 'security', 'published_steps'];
  const topics = ['fictional-booking', 'fictional-school'];
  const objects = ['invented-copper-booking', 'invented-willow-school'];
  const safety = ['declared-clear', 'declared-high-risk', 'unknown-not-clear'];
  const steps = ['inspect-fictional-booking', 'inspect-fictional-school'];
  function fail() { throw new Error('Fictional preview unavailable'); }
  function keys(value, expected) {
    if (!value || Object.getPrototypeOf(value) !== Object.prototype ||
        JSON.stringify(Object.keys(value).sort()) !== JSON.stringify([...expected].sort())) fail();
  }
  function integer(value, low, high) { if (!Number.isSafeInteger(value) || value < low || value > high) fail(); }
  function response(data) {
    keys(data, ['schema', 'synthetic_only', 'pagination', ...lanes]);
    if (data.schema !== 'g3b-fictional-read-v1' || data.synthetic_only !== true) fail();
    keys(data.pagination, ['limit', 'offset']);
    const {limit, offset} = data.pagination; integer(limit, 1, 20); integer(offset, 0, 128);
    for (const lane of lanes) {
      const page = data[lane]; keys(page, ['items', 'total', 'has_more']); integer(page.total, 0, 128);
      if (!Array.isArray(page.items) || page.items.length !== Math.min(limit, Math.max(0, page.total-offset)) ||
          typeof page.has_more !== 'boolean' || page.has_more !== (offset+page.items.length < page.total)) fail();
      const seen = new Set();
      for (const item of page.items) {
        let id;
        if (lane === 'published_steps') {
          keys(item, ['publication_id', 'step']);
          if (!topics.includes(item.publication_id) || !steps.includes(item.step)) fail();
          id = item.publication_id;
        } else {
          keys(item, ['source_id', 'provider', 'object_id', 'generation', 'topic', ...(lane === 'security' ? ['safety'] : [])]);
          if (typeof item.source_id !== 'string' || !/^[a-z][a-z0-9_-]{0,63}$/.test(item.source_id) ||
              item.provider !== 'fixture' || !objects.includes(item.object_id) || !topics.includes(item.topic) ||
              (lane === 'security' && !safety.includes(item.safety))) fail();
          integer(item.generation, 1, 1000000); id = JSON.stringify([item.source_id, item.object_id]);
        }
        if (seen.has(id)) fail(); seen.add(id);
      }
    }
    return data;
  }
  function validate(bundle) {
    keys(bundle, ['schema', 'synthetic_only', 'scenarios']);
    if (bundle.schema !== 'h2-offline-preview-v1' || bundle.synthetic_only !== true ||
        !Array.isArray(bundle.scenarios) || bundle.scenarios.length !== phases.length) fail();
    bundle.scenarios.forEach((scenario, n) => {
      keys(scenario, ['phase', 'peers']);
      if (scenario.phase !== phases[n] || !Array.isArray(scenario.peers) || scenario.peers.length !== peers.length) fail();
      scenario.peers.forEach((snapshot, p) => {
        keys(snapshot, ['peer', 'pages']);
        if (snapshot.peer !== peers[p] || !Array.isArray(snapshot.pages) || !snapshot.pages.length || snapshot.pages.length > 3) fail();
        snapshot.pages.forEach((data, page) => {
          response(data);
          if (data.pagination.limit !== 2 || data.pagination.offset !== page*2) fail();
          for (const lane of lanes) if (data[lane].total !== snapshot.pages[0][lane].total || data[lane].total > 6) fail();
        });
        const total = Math.max(...lanes.map(lane => snapshot.pages[0][lane].total));
        if (snapshot.pages.length !== Math.max(1, Math.ceil(total/2))) fail();
      });
    });
    return bundle;
  }
  function text(locale, key) {
    if (!i18n.LOCALES.includes(locale) || !Object.hasOwn(dictionaries[locale], 'h2.'+key)) fail();
    return dictionaries[locale]['h2.'+key];
  }
  function view(bundle, peer, phase, page, locale) {
    validate(bundle);
    if (!peers.includes(peer) || !phases.includes(phase) || !i18n.LOCALES.includes(locale)) fail();
    const snapshot = bundle.scenarios.find(s => s.phase === phase).peers.find(p => p.peer === peer);
    integer(page, 0, snapshot.pages.length-1);
    const data = snapshot.pages[page];
    return {peer, phase, locale, page, pages: snapshot.pages.length,
      limit: data.pagination.limit, offset: data.pagination.offset,
      lanes: lanes.map(lane => ({lane, title: text(locale, lane), total: data[lane].total,
        hasMore: data[lane].has_more, rows: data[lane].items.map(item => lane === 'published_steps'
          ? {identifier: item.publication_id, label: text(locale, item.step)}
          : {source: item.source_id, object: item.object_id, generation: item.generation,
             topic: text(locale, item.topic), ...(lane === 'security' ? {safety: text(locale, item.safety)} : {})})}))};
  }
  const exports = {validate, response, view, text, number: i18n.number, peers, phases, lanes};
  if (node) module.exports = exports; else root.FamilyH2Presentation = exports;
})(globalThis);
