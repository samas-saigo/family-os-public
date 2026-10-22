(function () {
  'use strict';
  const {Workbench, DAY} = globalThis.FamilyH0Model;
  const model = new Workbench();
  const i18n = globalThis.FamilyH1I18n, presentation = globalThis.FamilyH1Presentation;
  const preferences = new i18n.Preferences();
  // Tab-local appearance only: no household state, storage, service or authority.
  const systemAppearance = window.matchMedia('(prefers-color-scheme: dark)');
  let appearance = 'system';
  function applyAppearance() {
    document.documentElement.dataset.appearance = appearance;
    document.documentElement.dataset.theme = appearance === 'system' ? (systemAppearance.matches ? 'dark' : 'light') : appearance;
  }
  systemAppearance.addEventListener('change', () => { if (appearance === 'system') applyAppearance(); });
  applyAppearance();
  const locale = () => preferences.get(member);
  const tr = (key, values) => i18n.t(locale(), key, values);
  const number = value => i18n.number(locale(), value);
  let member = 'nora', view = 'home', query = '', category = 'all', assignee = 'all', page = 0, offersIntent = false, pendingBucket = 'active', showCompleted = false, draft = null, opened = null;
  const main = document.getElementById('main'), dialog = document.getElementById('detail-dialog'), body = document.getElementById('dialog-body');
  function labels() { return {home: tr('ui.home'), tasks: tr('ui.needs.action'), pending: tr('ui.pending.confirmation'), upcoming: tr('ui.upcoming'), security: tr('ui.security.review'), information: tr('ui.quiet.information'), offers: tr('ui.offers')}; }
  const icons = {home: '⌂', tasks: '✓', pending: '?', upcoming: '◷', security: '◇', information: '≋', offers: '✦'};
  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function button(text, fn, style = '') { const b = el('button', text, style); b.type = 'button'; b.addEventListener('click', fn); return b; }
  function announce(text) { const feedback = document.getElementById('feedback'); feedback.textContent = text; feedback.dataset.active = text ? 'true' : 'false'; }
  function clearFeedback() { announce(''); }
  function date(value) { return i18n.date(locale(), value); }
  function name(id) { return tr(`member.${id}`); }
  function badge(text, style = '') { return el('span', text, `badge ${style}`); }
  function note(text, warning = false) { return el('p', text, `note-box${warning ? ' warning' : ''}`); }
  function closeModal(message) {
    if (draft) model.cancel(draft);
    draft = null; opened = null; dialog.close(); body.replaceChildren();
    if (message) announce(message);
    document.getElementById('view-heading')?.focus();
  }
  dialog.addEventListener('cancel', event => { event.preventDefault(); closeModal(tr('ui.canceled.no.simulated.decision.was.saved')); });
  function modal(title) {
    if (draft) model.cancel(draft);
    draft = null; opened = null; dialog.dataset.mode = 'detail'; body.replaceChildren();
    const top = el('div', null, 'dialog-top'); top.append(el('small', tr('ui.fictional.details.no.real.action')), button('×', () => closeModal()));
    top.lastChild.setAttribute('aria-label', tr('ui.close.detail'));
    const heading = el('h2', title); heading.id = 'dialog-title';
    body.append(top, heading);
    if (!dialog.open) dialog.showModal();
  }
  function navigate(next) {
    document.getElementById('secondary-menu').open = false;
    if (dialog.open) closeModal();
    view = next; query = ''; category = 'all'; assignee = 'all'; page = 0; offersIntent = false; pendingBucket = 'active';
    document.getElementById('search').value = ''; document.getElementById('assignee').value = 'all';
    render(); document.getElementById('view-heading').focus();
  }
  function section(title, linkText, next) {
    const header = el('div', null, 'section-head'); header.append(el('h2', title));
    if (linkText) header.append(button(linkText, () => navigate(next)));
    return header;
  }
  function taskCard(t) {
    const card = el('article', null, `card task-line${t.status === 'completed' ? ' completed' : ''}`);
    const row = el('div', null, 'row'); row.append(badge(t.categoryLabel));
    if (t.status === 'completed') row.append(badge(tr('ui.simulated.complete'), 'neutral'));
    const meta = el('div', null, 'meta'); meta.append(el('span', name(t.assignee)), el('span', date(t.due)));
    card.append(row, el('h3', t.title), meta, button(tr('ui.inspect.accepted.step'), () => detail('task', t.id)));
    return card;
  }
  function itemCard(i, security = false) {
    const card = el('article', null, `card ${security ? 'security-line' : view === 'information' ? 'quiet-line' : 'pending-line'}`);
    const row = el('div', null, 'row'); row.append(badge(i.categoryLabel, security ? 'red' : 'amber'));
    row.append(badge(security ? tr(`safety.${i.safety}`) : i.disposition === 'archived' ? tr('state.archived') : i.disposition === 'deferred' ? tr('ui.deferred.unresolved') : i.disposition === 'needs-more-information' ? tr('ui.more.information.needed') : tr('ui.decision.needed'), 'neutral'));
    card.append(row, el('h3', i.title), el('p', security ? i.summary : i.uncertainty || i.summary), button(security ? tr('ui.inspect.safely') : tr('ui.inspect.question'), () => detail('item', i.id)));
    return card;
  }
  function eventRow(e) {
    const row = el('article', null, 'event'); const block = el('div', null, 'date-block');
    block.append(el('strong', number(Number(e.date.slice(8)))), el('span', i18n.month(locale(), e.date)));
    const content = el('div'); content.append(el('h3', e.title), el('p', `${e.dateType}${e.time ? ` · ${i18n.time(locale(), e.time)}` : ''}`));
    if (e.note) content.append(el('p', e.note));
    if (e.task) content.append(button(tr('ui.inspect.accepted.step'), () => detail('task', e.id)));
    row.append(block, content); return row;
  }
  function cards(rows, builder, wide = false, emptyKey = 'empty.information') {
    if (!rows.length) return el('p', tr(query.trim() || category !== 'all' || (['home', 'tasks'].includes(view) && assignee !== 'all') ? 'empty.filtered' : emptyKey), 'empty');
    const result = el('div', null, `cards${wide ? ' wide' : ''}`); rows.forEach(r => result.append(builder(r))); return result;
  }
  function detail(kind, id) {
    const data = presentation.detail(model, member, locale(), kind, id);
    if (!data) { closeModal(tr('ui.this.detail.is.unavailable.in.the')); return; }
    modal(data.title); opened = {kind, id};
    const context = el('details', null, 'context-details'); context.append(el('summary', tr('polish.context')));
    body.append(badge(kind === 'task' ? tr('ui.independently.accepted.fictional') : tr('format.safety', {risk: tr(`safety.${data.safety}`)}), kind === 'task' ? '' : data.safety === 'CLEAR' ? 'blue' : 'amber'));
    body.append(el('p', kind === 'task' ? data.step : data.summary, 'detail-text'));
    if (kind === 'task') {
      body.append(el('p', tr('format.owner', {owner: name(data.assignee), date: date(data.due), status: tr(`state.${data.status}`)}), 'detail-text'));
      context.append(el('p', tr('ui.authorized.supporting.evidence'), 'detail-label'));
      data.evidence.forEach(i => context.append(el('p', i.title, 'detail-text')));
      if (data.evidenceChanged) body.append(note(tr('ui.permitted.evidence.has.changed.since.acceptance'), true));
      context.append(note(tr('ui.only.evidence.permitted.in.this.view')));
      if (data.canEdit) {
        const assignment = el('div', null, 'assignment');
        const label = el('label', tr('ux.assignee')); label.htmlFor = 'task-assignee';
        const select = el('select'); select.id = 'task-assignee';
        data.assignees.forEach(id => {const option = el('option', name(id)); option.value = id; select.append(option);}); select.value = data.assignee;
        assignment.append(label, select, button(tr('ux.assign'), () => confirm('task-assignee', id, select.value))); body.append(assignment);
        body.append(button(data.status === 'completed' ? tr('ui.simulate.reopening') : tr('ui.simulate.completion'), () => confirm('task-status', id, data.status === 'completed' ? 'pending' : 'completed'), 'primary'));
      }
    } else {
      if (data.uncertainty) body.append(note(data.uncertainty, data.safety !== 'CLEAR'));
      if (data.step) { body.append(el('p', tr('ui.suggested.step.not.a.task'), 'detail-label'), el('p', data.step, 'detail-text')); }
      context.append(el('p', tr('format.evidence', {generation: number(data.generation), decision: tr(`state.${data.disposition}`)}), 'detail-text'));
      if (data.suspiciousText) body.append(el('code', data.suspiciousText, 'inert'));
      if (data.safety !== 'CLEAR') body.append(note(tr('ui.no.payment.sign.in.mailbox.move'), true));
      const actions = el('div', null, 'actions');
      if (data.canAccept && data.disposition !== 'archived') actions.append(button(tr('ui.accept.suggested.step'), () => confirm('accept', id), 'primary'));
      else if (data.kind === 'ACTION' || data.kind === 'QUESTION') body.append(el('p', tr('ui.task.acceptance.unavailable.independent.current.supporting'), 'detail-text'));
      if (data.canTriage) actions.append(button(tr('ui.defer.question'), () => confirm('defer', id)), button(tr('pending.archive'), () => confirm('archive', id)));
      if (data.canReopen) actions.append(button(tr('pending.reopen'), () => confirm('reopen', id)));
      body.append(actions);
    }
    if (data.history.length) {
      context.append(el('p', tr('ui.simulated.history'), 'detail-label'));
      const list = el('ul', null, 'history'); data.history.forEach(h => list.append(el('li', h.generation ? tr('format.historyEvidence', {action: h.action, actor: h.actor, generation: number(h.generation)}) : tr('format.historyTracking', {action: h.action, actor: h.actor, revision: number(h.revision)})))); context.append(list);
    }
    body.append(context);
    body.append(button(tr('ui.back.to.workbench'), () => closeModal(), 'subtle'));
  }
  function confirmations() { return {
    accept: [tr('ui.accept.a.fictional.household.step'), tr('ui.this.separately.accepts.the.suggested.step'), tr('ui.confirm.simulated.task.acceptance')],
    archive: [tr('pending.archive.title'), tr('pending.archive.text'), tr('pending.archive.save')],
    reopen: [tr('pending.reopen.title'), tr('pending.reopen.text'), tr('pending.reopen.save')],
    defer: [tr('ui.defer.this.household.question'), tr('ui.the.question.stays.unresolved.and.discoverable'), tr('ui.confirm.deferral')],
    'needs-info': [tr('ui.request.more.information.in.the.demo'), tr('ui.this.marks.the.question.unresolved.nothing'), tr('ui.confirm.needs.more.information')],
    'task-assignee': [tr('ux.assign.title'), tr('ux.assign.text'), tr('ux.assign.save')],
    'task-status': [tr('ui.change.fictional.tracking.status'), tr('ui.this.updates.shared.demo.tracking.only'), tr('ui.confirm.simulated.tracking.change')],
    sharing: [tr('ui.change.fictional.source.sharing'), tr('ui.this.changes.only.this.tab.s'), tr('ui.confirm.demo.sharing.change')],
    'evidence-change': [tr('ui.change.sample.evidence.generation'), tr('ui.a.new.fictional.generation.makes.safety'), tr('ui.confirm.sample.evidence.change')]
  }; }
  function confirm(type, id, extra = null) {
    const token = model.prepare(member, type, id, extra);
    if (!token) { announce(tr('ui.that.simulated.decision.is.unavailable.in')); return; }
    const origin = opened;
    let [title, text, label] = confirmations()[type];
    if (type === 'task-status') title = tr(extra === 'completed' ? 'polish.completeTitle' : 'polish.taskReopenTitle');
    if (type === 'sharing') title = tr(extra.allowed ? 'polish.shareTitle' : 'polish.revokeTitle');
    modal(title); dialog.dataset.mode = 'confirm'; draft = token;
    const target = type === 'sharing' ? model.sources(member).map(s => presentation.record(locale(), s, 'source')).find(s => s.id === id) : presentation.detail(model, member, locale(), ['task-status', 'task-assignee'].includes(type) ? 'task' : 'item', id);
    body.append(el('h3', target.title, 'confirmation-target'));
    body.append(el('p', text, 'detail-text'));
    if (type === 'accept') {
      const item = presentation.detail(model, member, locale(), 'item', id);
      body.append(note(tr('format.accept', {step: item.step, date: date(item.due), owner: model.state.items.find(i => i.id === id).publishTo.length === 1 ? name(member) : name('both')})));
    }
    if (type === 'sharing') body.append(note(tr(extra.allowed ? 'format.allow' : 'format.revoke', {member: name(extra.recipient)})));
    if (type === 'task-assignee') body.append(note(name(extra)));
    if (type === 'task-status') body.append(note(tr('format.tracking', {before: tr(`state.${model.detail(member, 'task', id).status}`), after: tr(`state.${extra}`)})));
    const actions = el('div', null, 'actions');
    actions.append(button(label, () => {
      const result = model.save(token, member, true); draft = null; closeModal(); render();
      const messages = {ACCEPTED: tr('ui.confirmed.a.fictional.step.was.separately'), CONFIRMED: () => successMessage(type, extra), CANCELED: tr('ui.canceled.nothing.was.saved'), STALE: tr('ui.not.saved.evidence.or.permissions.changed'), DENIED: tr('ui.not.saved.this.decision.is.unavailable'), REPLAY: tr('ui.already.recorded.no.duplicate.simulated.change')};
      announce(typeof messages[result.outcome] === 'function' ? messages[result.outcome]() : messages[result.outcome] || tr('ui.not.saved.this.decision.is.unavailable'));
    }, 'primary'), button(tr('ui.cancel.no.change'), () => closeModal(tr('ui.canceled.no.simulated.decision.was.saved'))));
    if (origin) actions.append(button(tr('ux.back'), () => { model.cancel(token); draft = null; if (origin.controls) controls(); else detail(origin.kind, origin.id); }));
    body.append(actions);
  }
  function successMessage(type, extra) {
    if (type === 'task-assignee') return tr('result.assignment', {owner: name(extra)});
    if (type === 'task-status') return tr(extra === 'completed' ? 'result.completed' : 'result.taskReopened');
    if (type === 'sharing') return tr(extra.allowed ? 'result.allowed' : 'result.revoked', {member: name(extra.recipient)});
    return tr(`result.${type}`);
  }
  function controls() {
    modal(tr('ui.demo.sharing.controls')); opened = {controls: true};
    body.append(el('p', tr('ux.settings.note'), 'detail-text'));
    const appearanceSection = el('section', null, 'appearance-settings');
    const appearanceTitle = el('h3', tr('appearance.title')); appearanceTitle.id = 'appearance-title';
    const appearanceSelect = el('select'); appearanceSelect.id = 'appearance-mode'; appearanceSelect.setAttribute('aria-labelledby', 'appearance-title');
    ['system', 'light', 'dark'].forEach(value => { const option = el('option', tr(`appearance.${value}`)); option.value = value; appearanceSelect.append(option); });
    appearanceSelect.value = appearance;
    appearanceSelect.addEventListener('change', event => {
      if (!['system', 'light', 'dark'].includes(event.target.value)) { event.target.value = appearance; return; }
      appearance = event.target.value; applyAppearance();
    });
    appearanceSection.append(appearanceTitle, appearanceSelect); body.append(appearanceSection);
    const connections = el('section', null, 'settings-connections');
    const unavailable = button(tr('ux.connect.disabled'), () => {}); unavailable.disabled = true;
    connections.append(el('h3', tr('ux.connections')), el('p', tr('ux.connections.note')), unavailable); body.append(connections);
    model.sources(member).map(source => presentation.record(locale(), source, 'source')).forEach(source => {
      const row = el('div', null, 'source-row'); row.append(el('h3', source.title), el('p', source.readers.length === 2 ? tr('ui.shared.with.both.adults') : tr('ui.visible.to.this.member.only')));
      if (source.canManage) {
        const other = member === 'nora' ? 'julian' : 'nora'; const allowed = source.readers.includes(other);
        row.append(button(tr(allowed ? 'format.revokeButton' : 'format.allowButton', {member: name(other)}), () => confirm('sharing', source.id, {recipient: other, allowed: !allowed})));
      } else row.append(el('p', tr('ui.read.access.does.not.grant.sharing')));
      body.append(row);
    });
    const sample = model.detail(member, 'item', 'workshop');
    if (sample && model.sources(member).find(s => s.id === sample.source)?.canManage) {
      body.append(el('p', tr('ui.optional.stale.evidence.probe'), 'detail-label'), button(tr('ui.change.the.workshop.evidence.sample'), () => confirm('evidence-change', 'workshop')));
    }
    body.append(button(tr('ui.close.controls'), () => closeModal(), 'subtle'));
  }
  function localizeChrome() {
    document.documentElement.lang = locale();
    document.title = tr('chrome.title');
    document.querySelectorAll('[data-i18n]').forEach(node => { node.textContent = tr(node.dataset.i18n); });
    document.querySelectorAll('[data-i18n-label]').forEach(node => { node.setAttribute('aria-label', tr(node.dataset.i18nLabel)); });
    document.getElementById('search').placeholder = tr('chrome.placeholder');
    document.getElementById('language').value = locale();
    document.getElementById('member').querySelectorAll('option').forEach(node => { node.textContent = name(node.value); });
  }
  let compact = null;
  const sidebarBottom = document.querySelector('.sidebar-bottom'), preferencesPanel = document.querySelector('.preferences');
  function responsiveChrome() {
    const mobile = window.innerWidth <= 730;
    const secondary = document.querySelector('.nav-extra'), menu = document.getElementById('secondary-menu');
    if (mobile) document.getElementById('secondary-body').append(secondary, sidebarBottom, preferencesPanel);
    else { document.getElementById('navigation').append(secondary); document.querySelector('.sidebar').append(sidebarBottom); document.querySelector('.topbar').append(preferencesPanel); }
    if (compact !== mobile) { menu.open = false; document.getElementById('search-controls').open = false; compact = mobile; }
  }
  window.addEventListener('resize', responsiveChrome);
  // Browsing clears transient results; callers announce new outcomes after rendering.
  function render() {
    clearFeedback();
    localizeChrome();
    main.dataset.view = view;
    const p = presentation.project(model, member, locale(), {view, query, category, assignee, page, offersIntent, pendingBucket}); page = p.page;
    document.querySelector('.nav-extra')?.remove();
    const nav = document.getElementById('navigation'); nav.replaceChildren();
    const primaryNav = el('div', null, 'nav-main'), secondaryNav = el('div', null, 'nav-extra'); nav.append(primaryNav, secondaryNav);
    Object.keys(labels()).forEach(key => {
      const b = button('', () => navigate(key)); b.append(el('span', icons[key], 'icon'), el('span', labels()[key])); b.firstChild.setAttribute('aria-hidden', 'true');
      if (key === view) b.setAttribute('aria-current', 'page');
      const count = key === 'tasks' ? p.counts.tasks : key === 'pending' ? p.counts.pending : key === 'security' ? p.counts.security : null;
      if (count !== null) b.append(el('span', number(count), 'count'));
      b.dataset.view = key;
      b.classList.add(['information', 'offers'].includes(key) ? 'nav-secondary' : 'nav-primary');
      (['information', 'offers'].includes(key) ? secondaryNav : primaryNav).append(b);
    });
    responsiveChrome();
    const selector = document.getElementById('category'); selector.replaceChildren();
    [['all', tr('ui.all.categories')], ...p.categories.map(c => [c, tr(`category.${c}`)])].forEach(([value, text]) => { const option = el('option', text); option.value = value; selector.append(option); });
    if (!p.categories.includes(category)) category = 'all'; selector.value = category;
    document.getElementById('assignee').hidden = !['home', 'tasks'].includes(view);
    main.replaceChildren();
    const hero = el('div', null, 'hero'), intro = el('div'); intro.append(el('p', tr('ux.scope', {date: i18n.date(locale(), DAY, view !== 'home'), member: name(member)}), 'eyebrow'));
    const heading = el('h1', view === 'home' ? tr('ui.a.little.less.to.keep.in') : labels()[view]); heading.id = 'view-heading'; heading.tabIndex = -1; intro.append(heading);
    const subtitles = {home: tr('ui.one.shared.household.the.accepted.steps'), tasks: tr('ui.separately.accepted.fictional.steps.shared.between'), pending: tr('ui.a.decision.queue.not.another.inbox'), upcoming: tr('ui.known.fictional.dates.only.calendar.facts'), security: tr('ui.inspect.concerns.independently.unknown.is.not'), information: tr('ui.useful.to.know.with.no.assumed'), offers: tr('ui.only.when.you.ask.no.promotional')};
    if (view !== 'home') intro.append(el('p', view === 'pending' ? tr('polish.pendingIntro') : subtitles[view], 'subtitle')); hero.append(intro);

    main.append(hero);
    if (query) main.append(el('p', tr('format.search', {query}), 'subtitle'));
    if (view === 'home') {
      const stats = el('div', null, 'stats'); [[p.counts.tasks, tr('ui.accepted.steps.open'), 'tasks'], [p.counts.pending, tr('ui.unresolved.questions'), 'pending'], [p.counts.upcoming, tr('ui.known.dates'), 'upcoming'], [p.counts.security, tr('ux.security.count'), 'security']].forEach(([value, label, next]) => { const stat = button('', () => navigate(next), 'stat'); stat.append(el('strong', number(value)), el('span', label)); stats.append(stat); }); main.append(stats);
      const columns = el('div', null, 'columns'), left = el('section'), right = el('section');
      left.append(section(tr('ui.the.next.small.steps'), tr('ui.all.accepted.steps'), 'tasks'), cards(p.tasks.filter(t => t.status !== 'completed').slice(0, 3), taskCard, false, 'empty.tasks'));
      const pending = el('section', null, 'section-spaced'); pending.append(section(tr('ui.a.few.decisions.to.make'), tr('format.allPending'), 'pending'), cards(p.pending.slice(0, 2), i => itemCard(i), false, 'empty.active')); left.append(pending);
      right.append(section(tr('ui.coming.up'), tr('ui.all.known.dates'), 'upcoming')); p.upcoming.slice(0, 3).forEach(e => right.append(eventRow(e)));
      const safety = el('section', null, 'section-spaced'); safety.append(section(tr('ui.safety.stays.separate'), tr('format.inspectCount'), 'security')); right.append(safety);
      columns.append(left, right); main.append(columns);
    } else if (view === 'tasks') {
      main.append(button(showCompleted ? tr('ui.hide.simulated.completed.steps') : tr('ui.show.simulated.completed.steps'), () => { showCompleted = !showCompleted; render(); }, 'completed-toggle'));
      main.append(cards(p.tasks.filter(t => showCompleted || t.status !== 'completed'), taskCard, true, showCompleted || p.counts.completed === 0 ? 'empty.allTasks' : 'empty.tasks'));
    } else if (view === 'pending') {
      const buckets = el('div', null, 'pending-buckets'); buckets.setAttribute('aria-label', tr('pending.categories'));
      ['active', 'later', 'archived'].forEach(b => {
        const control = button('', () => { pendingBucket = b; page = 0; render(); });
        control.append(el('span', tr(`pending.${b}`)), el('span', number(p.pendingCounts[b]), 'bucket-count'));
        control.setAttribute('aria-label', tr('pending.bucket', {name: tr(`pending.${b}`), count: number(p.pendingCounts[b])}));
        control.dataset.bucket = b; control.setAttribute('aria-pressed', String(b === pendingBucket)); buckets.append(control);
      });
      main.append(buckets, cards(p.pending, i => itemCard(i), true, `empty.${pendingBucket}`));
      const pages = el('div', null, 'pagination'); const prev = button(tr('ui.previous'), () => { page -= 1; render(); }); prev.disabled = p.page === 0;
      const next = button(tr('ui.next'), () => { page += 1; render(); }); next.disabled = p.page >= p.pendingPages - 1;
      pages.append(el('span', tr('format.backlog', {count: number(p.pendingTotal)})), prev, el('span', tr('format.page', {page: number(p.page + 1), pages: number(p.pendingPages)})), next); main.append(pages);
    } else if (view === 'upcoming') {
      if (!p.upcoming.length) main.append(cards([], eventRow, false, 'empty.upcoming')); else p.upcoming.forEach(e => main.append(eventRow(e)));
    } else if (view === 'security') main.append(cards(p.security, i => itemCard(i, true), true, 'empty.security'));
    else if (view === 'information') main.append(cards(p.information, i => itemCard(i), true));
    else if (!offersIntent) {
      const gate = el('section', null, 'offers-gate'); gate.append(el('div', '✦', 'symbol'), el('h2', tr('ui.useful.offers.on.your.terms')), button(tr('ui.find.fictional.offers'), () => { offersIntent = true; render(); }, 'primary')); main.append(gate);
    } else {
      main.append(cards(p.offers, i => {
        const card = el('article', null, 'card quiet-line'); card.append(badge(i.categoryLabel), el('h3', i.merchant), el('p', i.preference), el('div', i.coupon, 'coupon'), el('p', tr('format.offer', {expiry: i.expiry < DAY ? tr('ui.expired') : tr('ui.known.fictional.expiry'), date: date(i.expiry), eligibility: i.eligibility})), button(tr('ui.inspect.fictional.offer'), () => detail('item', i.id))); return card;
      }, true, 'empty.offers'));
    }
  }
  function changeLanguage(event) {
    document.getElementById('secondary-menu').open = false;
    const wasDraft = !!draft, previous = opened;
    if (dialog.open) closeModal();
    preferences.set(member, event.target.value); query = ''; page = 0;
    document.getElementById('search').value = '';
    render();
    if (previous?.controls) controls();
    else if (previous) detail(previous.kind, previous.id);
    announce(tr(wasDraft ? 'locale.changed' : 'locale.ready'));
    if (!dialog.open) {
      // The single picker is hidden when the compact menu closes. Keep focus reachable.
      (window.innerWidth <= 730 ? document.querySelector('#secondary-menu>summary') : document.getElementById('language')).focus();
    }
  }
  document.getElementById('language').addEventListener('change', changeLanguage);
  document.getElementById('search').addEventListener('input', event => { query = event.target.value; page = 0; render(); });
  document.getElementById('category').addEventListener('change', event => { category = event.target.value; page = 0; render(); });
  document.getElementById('assignee').addEventListener('change', event => { assignee = event.target.value; page = 0; render(); });
  document.getElementById('member').addEventListener('change', event => {
    if (dialog.open) closeModal(); member = event.target.value; showCompleted = false;
    navigate('home'); announce(tr('format.memberChanged', {member: name(member)}));
  });
  document.getElementById('demo-controls').addEventListener('click', () => { document.getElementById('secondary-menu').open = false; controls(); });
  document.getElementById('reset').addEventListener('click', () => {
    document.getElementById('secondary-menu').open = false;
    modal(tr('ui.reset.all.fictional.changes')); body.append(el('p', tr('ui.this.clears.only.in.memory.demo'), 'detail-text'));
    const actions = el('div', null, 'actions'); actions.append(button(tr('ui.confirm.demo.reset'), () => { model.reset(); preferences.reset(); appearance = 'system'; applyAppearance(); closeModal(); member = 'nora'; document.getElementById('member').value = 'nora'; showCompleted = false; navigate('home'); announce(tr('ui.fictional.state.reset.nothing.was.persisted')); }, 'primary'), button(tr('ui.cancel.keep.demo.state'), () => closeModal())); body.append(actions);
  });
  render();
})();
