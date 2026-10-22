/* Authorization remains in H0 model. Translate only its permitted DTOs. */
(function (root) {
  'use strict';
  const i18n = typeof module !== 'undefined' && module.exports ? require('./i18n.js') : root.FamilyH1I18n;
  const PAGE_SIZE = 3;
  function record(locale, data, kind) {
    const output = {...data};
    const accepted = kind === 'task' && data.id.startsWith('accepted-');
    const id = accepted ? data.id.slice('accepted-'.length) : data.id;
    const fields = kind === 'source' ? ['title'] : kind === 'task' ? ['title', 'step'] : kind === 'event' ? ['title', 'note'] : ['title', 'step', 'summary', 'uncertainty', 'preference', 'eligibility'];
    fields.forEach(field => {
      if (data[field] !== undefined) output[field] = i18n.t(locale, `fixture.${id}.${accepted && field === 'title' ? 'step' : field}`);
    });
    if (data.category) output.categoryLabel = i18n.t(locale, `category.${data.category}`);
    if (data.dateType) output.dateType = i18n.t(locale, data.task ? 'format.taskDate' : 'format.calendar');
    if (data.suspiciousText) output.suspiciousText = data.suspiciousText.split(' · ')[0] + ' · ' + i18n.t(locale, 'inertLabel');
    return output;
  }
  function detail(model, member, locale, kind, id) {
    const data = model.detail(member, kind, id);
    if (!data) return null;
    const output = record(locale, data, kind);
    if (data.evidence) output.evidence = data.evidence.map(i => record(locale, i, 'item'));
    // History actor strings are authored H0 names, not trusted identities.
    output.history = data.history.map(h => ({...h, action: i18n.t(locale, `history.${h.action}`), actor: i18n.t(locale, `member.${({Nora: 'nora', Julian: 'julian'})[h.actor]}`)}));
    return output;
  }
  function project(model, member, locale, {view = 'home', query = '', category = 'all', assignee = 'all', page = 0, offersIntent = false, pendingBucket = 'active'} = {}) {
    // First obtain only currently permitted fields; hidden content is never translated
    // or examined for consistency/search. No second routing or grant-policy engine.
    const base = model.projection(member, {view, assignee, offersIntent, pendingBucket});
    if (typeof query !== 'string' || query.length > 80 || !Number.isInteger(page) || page < 0) throw new Error('Presentation unavailable');
    const pending = [...base.pending];
    for (let n = 1; n < base.pendingPages; n++) pending.push(...model.projection(member, {view, assignee, offersIntent, pendingBucket, page: n}).pending);
    const lists = {tasks: base.tasks.map(r => record(locale, r, 'task')), pending: pending.map(r => record(locale, r, 'item')),
      security: base.security.map(r => record(locale, r, 'item')), information: base.information.map(r => record(locale, r, 'item')),
      offers: base.offers.map(r => record(locale, r, 'item')), upcoming: base.upcoming.map(r => record(locale, r, r.task ? 'task' : 'event'))};
    const q = query.trim().toLocaleLowerCase(locale);
    const matches = r => (!q || [r.title, r.step, r.summary, r.merchant, r.categoryLabel].filter(Boolean).join(' ').toLocaleLowerCase(locale).includes(q)) && (category === 'all' || r.category === category);
    const filtered = Object.fromEntries(Object.entries(lists).map(([key, values]) => [key, values.filter(matches)]));
    const pages = Math.max(1, Math.ceil(filtered.pending.length / PAGE_SIZE));
    const current = Math.min(page, pages - 1);
    return {...base, ...filtered, pending: filtered.pending.slice(current * PAGE_SIZE, (current + 1) * PAGE_SIZE), pendingTotal: filtered.pending.length,
      pendingPages: pages, page: current};
  }
  const api = {record, detail, project};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.FamilyH1Presentation = api;
})(globalThis);
