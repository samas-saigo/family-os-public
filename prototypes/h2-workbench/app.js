(function() {
  'use strict';
  const p = globalThis.FamilyH2Presentation;
  const main = document.getElementById('main');
  const state = {peer: 'iris', phase: 'initial', page: 0, locale: 'zh-CN', lane: 'observations'};
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  const t = key => p.text(state.locale, key);
  const number = value => p.number(state.locale, value);
  function failed() {
    main.replaceChildren(element('p', state.locale === 'en-US' ? 'Fictional preview unavailable.' : '虚构预览不可用；不会显示部分记录。', 'empty'));
    document.getElementById('navigation').replaceChildren();
  }
  function render() {
    try {
      const view = p.view(globalThis.FamilyH2Snapshot, state.peer, state.phase, state.page, state.locale);
      document.documentElement.lang = state.locale; document.title = t('title');
      for (const id of ['tagline', 'household', 'notice', 'gap', 'warning', 'footer', 'skip']) document.getElementById(id).textContent = t(id);
      document.getElementById('navigation').setAttribute('aria-label', t('navigation'));
      for (const [id, key] of [['peer', 'peer'], ['language', 'language'], ['phase', 'phase']]) {
        document.getElementById(id+'-label').textContent = t(key);
        document.getElementById(id).setAttribute('aria-label', t(key));
      }
      for (const peer of p.peers) document.querySelector('#peer option[value="'+peer+'"]').textContent = t(peer);
      for (const phase of p.phases) document.querySelector('#phase option[value="'+phase+'"]').textContent = t(phase);
      const navigation = document.getElementById('navigation'); navigation.replaceChildren();
      for (const lane of view.lanes) {
        const button = element('button', lane.title+' · '+number(lane.total));
        button.setAttribute('aria-current', lane.lane === state.lane ? 'page' : 'false');
        button.addEventListener('click', () => {state.lane = lane.lane; render();}); navigation.append(button);
      }
      const lane = view.lanes.find(l => l.lane === state.lane);
      const hero = element('div', undefined, 'hero'); hero.append(element('h1', lane.title), element('p', t('intro')));
      const stats = element('div', undefined, 'stats');
      for (const [label, value] of [['total', lane.total], ['shown', lane.rows.length], ['offset', view.offset]]) {
        const stat = element('div', undefined, 'stat'); stat.append(element('strong', number(value)), element('span', t(label))); stats.append(stat);
      }
      const cards = element('div', undefined, 'cards wide');
      for (const row of lane.rows) {
        const card = element('article', undefined, 'card');
        card.append(element('h3', row.label || t(state.lane === 'security' ? 'security-record' : 'record')));
        if (state.lane === 'published_steps') {
          card.append(element('p', t('step-warning')), element('p', t('publication')+': '+row.identifier, 'meta'));
        } else {
          for (const [field, value] of [['source', row.source], ['object', row.object], ['generation', number(row.generation)], ['topic', row.topic]])
            card.append(element('p', t(field)+': '+value, 'meta'));
          if (row.safety) card.append(element('p', row.safety));
        }
        cards.append(card);
      }
      if (!lane.rows.length) cards.append(element('p', t('empty'), 'empty'));
      const pagination = element('div', undefined, 'section-head');
      for (const [label, delta] of [['previous', -1], ['next', 1]]) {
        const button = element('button', t(label));
        button.disabled = state.page+delta < 0 || state.page+delta >= view.pages;
        button.addEventListener('click', () => {state.page += delta; render();}); pagination.append(button);
      }
      main.replaceChildren(hero, stats, cards, element('p', t(lane.hasMore ? 'more' : 'last')),
        ...(state.lane === 'security' ? [element('p', t('safety-note'))] : []), pagination);
    } catch (_) {failed();}
  }
  for (const [id, property] of [['peer', 'peer'], ['phase', 'phase'], ['language', 'locale']])
    document.getElementById(id).addEventListener('change', event => {state[property] = event.target.value; state.page = 0; render();});
  render();
})();
