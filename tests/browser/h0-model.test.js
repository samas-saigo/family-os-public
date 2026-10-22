'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {Workbench, VIEWS, PAGE_SIZE} = require('../../prototypes/h0-workbench/model.js');
const fixtures = require('../../prototypes/h0-workbench/fixtures.js');
const fresh = () => new Workbench();
function apply(m, type, id, extra = null, member = 'nora') { const receipt = m.prepare(member, type, id, extra); assert.ok(receipt); return m.save(receipt, member, true); }

test('seven views are bounded permitted projections', () => {
  const m = fresh(); assert.equal(VIEWS.length, 7);
  for (const view of VIEWS) assert.equal(m.projection('nora', {view}).view, view);
  assert.throws(() => m.projection('nora', {view: 'inbox'}));
});
test('default accepted tasks are not classified messages', () => {
  const m = fresh(); const p = m.projection('nora');
  assert.ok(p.tasks.every(t => t.authority === 'separately-accepted'));
  assert.equal(p.tasks.length, 4); assert.ok(!p.tasks.some(t => t.title.includes('offer')));
});
test('ordinary and expired advertising never enters Pending', () => {
  const m = fresh(); const pending = [];
  for (let page = 0; page < 4; page++) pending.push(...m.projection('nora', {view: 'pending', page}).pending);
  assert.ok(!pending.some(i => i.kind === 'PROMOTION')); assert.equal(new Set(pending.map(i => i.id)).size, 8);
});
test('offers are invisible without exact explicit intent', () => {
  const m = fresh(); for (const intent of [undefined, false, 1, 'true']) assert.equal(m.projection('nora', {view: 'offers', offersIntent: intent}).offers.length, 0);
  assert.equal(m.projection('nora', {view: 'offers', offersIntent: true}).offers.length, 3);
});
test('suspicious and unknown promotions never become offers or tasks', () => {
  const m = fresh(); const p = m.projection('nora', {offersIntent: true});
  assert.ok(!p.offers.some(i => ['promo-risk', 'promo-unknown'].includes(i.id)));
  assert.equal(m.prepare('nora', 'accept', 'promo-risk'), null); assert.equal(m.prepare('nora', 'accept', 'promo-unknown'), null);
  assert.ok(p.security.some(i => i.id === 'promo-unknown'));
});
test('suspicious payment and sign-in claims cannot become actionable tasks', () => {
  const m = fresh(); for (const id of ['login-risk', 'payment-risk', 'unknown-school', 'possible-hold']) assert.equal(m.prepare('nora', 'accept', id), null);
});
test('review and task acceptance are independent human intentions', () => {
  const m = fresh(); const count = m.state.tasks.length;
  assert.equal(apply(m, 'review', 'workshop').outcome, 'CONFIRMED'); assert.equal(m.state.tasks.length, count);
  assert.equal(m.detail('nora', 'item', 'workshop').review, 'confirmed');
  assert.equal(apply(m, 'accept', 'workshop').outcome, 'ACCEPTED'); assert.equal(m.state.tasks.length, count + 1);
});
test('ordinary reviews never revoke simulated acceptance or clear safety', () => {
  const m = fresh(); apply(m, 'accept', 'workshop'); apply(m, 'review', 'workshop'); apply(m, 'review', 'workshop');
  assert.ok(m.projection('nora').tasks.some(t => t.id === 'accepted-workshop'));
  assert.ok(!m.projection('nora').pending.some(i => i.id === 'workshop'));
  apply(m, 'review', 'login-risk'); assert.equal(m.detail('nora', 'item', 'login-risk').safety, 'HIGH_RISK');
});
test('canceled and unconfirmed drafts make no changes', () => {
  const m = fresh(); const before = structuredClone(m.state);
  for (const confirm of [false, undefined, 1, 'true']) { const token = m.prepare('nora', 'accept', 'workshop'); assert.equal(m.save(token, 'nora', confirm).outcome, 'CANCELED'); }
  assert.deepEqual(m.state, before); assert.equal(m.itemHistory.size, 0);
});
test('cancel prevents subsequent reuse of the draft', () => {
  const m = fresh(); const token = m.prepare('nora', 'accept', 'workshop'); m.cancel(token);
  assert.equal(m.save(token, 'nora', true).outcome, 'DENIED');
});
test('copied or other-member receipts cannot grant authority', () => {
  const m = fresh(); const token = m.prepare('nora', 'accept', 'workshop');
  assert.equal(m.save({...token}, 'nora', true).outcome, 'DENIED'); assert.equal(m.save(token, 'julian', true).outcome, 'DENIED');
});
test('duplicate confirmed delivery has one task and one history entry', () => {
  const m = fresh(); const token = m.prepare('nora', 'accept', 'workshop');
  assert.equal(m.save(token, 'nora', true).outcome, 'ACCEPTED'); assert.equal(m.save(token, 'nora', true).outcome, 'REPLAY');
  assert.equal(m.state.tasks.filter(t => t.id === 'accepted-workshop').length, 1); assert.equal(m.itemHistory.get('workshop').length, 1);
});
test('evidence change and later apparent revert never validate old acceptance', () => {
  const m = fresh(); const token = m.prepare('nora', 'accept', 'workshop'); const original = m.state.items.find(i => i.id === 'workshop').title;
  apply(m, 'evidence-change', 'workshop');
  assert.equal(m.save(token, 'nora', true).outcome, 'STALE'); assert.equal(m.prepare('nora', 'accept', 'workshop'), null);
  const i = m.state.items.find(i => i.id === 'workshop'); i.title = original; i.generation += 1;
  assert.equal(m.save(token, 'nora', true).outcome, 'STALE');
});
test('source read revocation removes items, dates, categories and detail', () => {
  const m = fresh(); const before = m.projection('julian');
  apply(m, 'sharing', 'notices', {recipient: 'julian', allowed: false});
  const after = m.projection('julian'); assert.ok(after.counts.pending < before.counts.pending); assert.ok(after.counts.security < before.counts.security);
  assert.equal(m.detail('julian', 'item', 'workshop'), null); assert.ok(!m.sources('julian').some(s => s.id === 'notices'));
  assert.ok(!m.projection('julian', {query: 'workshop'}).pending.some(i => i.id === 'workshop'));
});
test('shared published task fields survive source revocation without private provenance', () => {
  const m = fresh(); const before = m.projection('julian').tasks;
  apply(m, 'sharing', 'notices', {recipient: 'julian', allowed: false});
  assert.deepEqual(m.projection('julian').tasks, before);
  assert.equal(m.detail('julian', 'task', 'task-school').evidence.length, 0);
  assert.ok(!JSON.stringify(m.projection('nora').tasks).includes('picnic-note'));
  assert.equal(m.detail('nora', 'task', 'task-bag').evidence.length, 0);
});
test('publication revocation is independent from source access', () => {
  const m = fresh(); m.state.tasks.find(t => t.id === 'task-school').readers = ['nora'];
  assert.equal(m.detail('julian', 'task', 'task-school'), null); assert.ok(m.detail('julian', 'item', 'registration'));
});
test('private evidence cannot influence task search or published fields', () => {
  const m = fresh(); const before = m.projection('nora');
  const i = m.state.items.find(i => i.id === 'picnic-note'); i.title = 'SECRET HIDDEN QUERY'; i.safety = 'HIGH_RISK'; i.generation += 1;
  assert.deepEqual(m.projection('nora'), before); assert.equal(m.projection('nora', {query: 'SECRET HIDDEN QUERY'}).tasks.length, 0);
});
test('hidden populations do not influence ordering, paging or permitted counts', () => {
  const m = fresh(); const before = m.projection('julian', {view: 'pending', page: 1});
  const item = m.state.items.find(i => i.id === 'nora-class');
  for (let n = 0; n < 200; n++) m.state.items.push({...item, id: `hidden-${n}`, title: `hidden${n}`, category: 'Secret category'});
  assert.deepEqual(m.projection('julian', {view: 'pending', page: 1}), before);
});
test('equal source and publication grants yield one equivalent shared view', () => {
  const m = fresh(); m.state.sources.filter(s => s.id.endsWith('-notes')).forEach(s => { s.readers = []; });
  m.state.tasks.filter(t => t.readers.length === 1).forEach(t => { t.readers = []; });
  assert.deepEqual(m.projection('nora'), m.projection('julian'));
});
test('persona selection does not manufacture source management rights', () => {
  const m = fresh(); assert.equal(m.prepare('julian', 'sharing', 'notices', {recipient: 'nora', allowed: false}), null);
  assert.ok(m.prepare('julian', 'sharing', 'community', {recipient: 'nora', allowed: false}));
  assert.equal(m.prepare('nora', 'sharing', 'community', {recipient: 'julian', allowed: false}), null);
});
test('revoked readers cannot save or replay source decisions', () => {
  const m = fresh(); const receipt = m.prepare('julian', 'review', 'workshop'); m.save(receipt, 'julian', true);
  const pending = m.prepare('julian', 'accept', 'workshop'); apply(m, 'sharing', 'notices', {recipient: 'julian', allowed: false});
  assert.equal(m.save(receipt, 'julian', true).outcome, 'DENIED'); assert.equal(m.save(pending, 'julian', true).outcome, 'DENIED');
});
test('independently supported dates exclude promotional expiry and uncertain questions', () => {
  const m = fresh(); const upcoming = m.projection('nora').upcoming;
  assert.ok(upcoming.every(e => e.date && ['Confirmed calendar fact', 'Published task date'].includes(e.dateType)));
  assert.ok(!upcoming.some(e => ['garden-offer', 'expired-offer', 'visit', 'unknown-school'].includes(e.id)));
});
test('deferred and more-information questions remain in the full backlog', () => {
  const m = fresh(); const before = m.projection('nora').pendingTotal;
  apply(m, 'defer', 'visit'); apply(m, 'needs-info', 'clinic-question');
  assert.equal(m.projection('nora').pendingTotal, before - 1); assert.equal(m.projection('nora', {view: 'pending', pendingBucket: 'later'}).pendingTotal, 1); assert.equal(m.detail('nora', 'item', 'visit').disposition, 'deferred');
});
test('pagination is deterministic bounded and does not discard overflow', () => {
  const m = fresh(); const first = m.projection('nora', {view: 'pending'}); const all = [];
  for (let page = 0; page < first.pendingPages; page++) { const p = m.projection('nora', {view: 'pending', page}); assert.ok(p.pending.length <= PAGE_SIZE); all.push(...p.pending); }
  assert.equal(all.length, first.pendingTotal); assert.equal(new Set(all.map(i => i.id)).size, all.length);
});
test('shared tracking is one state for both peers, never an actual completed action', () => {
  const m = fresh(); apply(m, 'task-status', 'task-school', 'completed');
  assert.equal(m.detail('nora', 'task', 'task-school').status, 'completed'); assert.equal(m.detail('julian', 'task', 'task-school').status, 'completed');
  assert.equal(m.detail('nora', 'item', 'registration').review, 'unreviewed'); assert.equal(m.projection('nora').counts.completed, 1);
});
test('concurrent stale task intentions cannot overwrite a newer tracking state', () => {
  const m = fresh(); const receipt = m.prepare('nora', 'task-status', 'task-school', 'completed');
  apply(m, 'task-status', 'task-school', 'pending', 'julian'); assert.equal(m.save(receipt, 'nora', true).outcome, 'STALE');
});
test('reset restores fixture state, annotations and permissions without persistence', () => {
  const m = fresh(); const before = m.projection('nora'); apply(m, 'accept', 'workshop'); apply(m, 'sharing', 'notices', {recipient: 'julian', allowed: false}); m.reset();
  assert.deepEqual(m.projection('nora'), before); assert.equal(m.itemHistory.size, 0);
});
test('viewing does not mutate decisions or history', () => {
  const m = fresh(); const before = structuredClone(m.state); for (const view of VIEWS) m.projection('nora', {view}); m.detail('nora', 'item', 'workshop');
  assert.deepEqual(m.state, before); assert.equal(m.itemHistory.size, 0);
});
test('unknown principals and unbounded queries fail closed', () => {
  const m = fresh(); for (const member of ['other', '__proto__', null, {person: 'nora'}]) assert.throws(() => m.projection(member));
  for (const options of [{page: -1}, {page: .5}, {query: 'x'.repeat(81)}]) assert.throws(() => m.projection('nora', options));
});
test('changing then reverting a promotion cannot create Pending or imply clearance', () => {
  const m = fresh(); apply(m, 'evidence-change', 'garden-offer', null, 'julian');
  assert.ok(!m.projection('julian', {offersIntent: true}).offers.some(i => i.id === 'garden-offer'));
  assert.ok(!m.projection('julian').pending.some(i => i.id === 'garden-offer'));
  assert.ok(m.projection('julian').security.some(i => i.id === 'garden-offer'));
  m.state.items.find(i => i.id === 'garden-offer').generation += 1;
  assert.equal(m.detail('julian', 'item', 'garden-offer').safety, 'UNKNOWN');
});

test('changed permitted evidence warns without reviving old action authority', () => {
  const m = fresh(); apply(m, 'accept', 'workshop'); apply(m, 'evidence-change', 'workshop');
  assert.equal(m.detail('nora', 'task', 'accepted-workshop').evidenceChanged, true);
  assert.equal(m.prepare('nora', 'accept', 'workshop'), null);
  apply(m, 'sharing', 'notices', {recipient: 'julian', allowed: false});
  const task = m.detail('julian', 'task', 'accepted-workshop');
  assert.equal(task.evidenceChanged, false); assert.equal(task.evidence.length, 0);
  assert.ok(task.title); // Independent published continuity, no hidden freshness signal.
});
