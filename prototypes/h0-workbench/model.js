/* Disposable UI state, not authentication or a replacement for G2a/G2b2. */
(function (root) {
  'use strict';
  const data = typeof module !== 'undefined' && module.exports ? require('./fixtures.js') : root.FamilyH0Fixtures;
  const VIEWS = ['home', 'tasks', 'pending', 'upcoming', 'security', 'information', 'offers'];
  const PAGE_SIZE = 3;
  const PERSONAL = ['defer', 'needs-info', 'archive', 'reopen'];
  class Workbench {
    constructor(seed = data.seed()) { this.initial = structuredClone(seed); this.reset(); }
    reset() { this.state = structuredClone(this.initial); this.receipts = new Map(); this.itemHistory = new Map(); this.decisions = new Map(); }
    member(id) { return typeof id === 'string' && Object.hasOwn(this.state.members, id); }
    source(id) { return this.state.sources.find(s => s.id === id); }
    canRead(member, source) { return this.member(member) && !!this.source(source)?.readers.includes(member); }
    currentSafety(item) { return item.safetyGeneration === item.generation ? item.safety : 'UNKNOWN'; }
    safe(item) { return this.currentSafety(item) === 'CLEAR'; }
    visibleItems(member) { return this.state.items.filter(i => this.canRead(member, i.source)); }
    visibleTasks(member) { return this.state.tasks.filter(t => this.member(member) && t.readers.includes(member)); }
    taskProjection(t) {
      return {id: t.id, title: t.title, step: t.step, category: t.category, assignee: t.assignee,
        due: t.due, status: t.status, revision: t.revision, authority: t.authority};
    }
    decision(member, item) {
      const personal = this.decisions.get(member)?.get(item.id);
      // Personal triage binds one exact generation; a changed/reverted observation
      // needs a new decision. Shared task acceptance remains a separate authority.
      return personal?.generation === item.generation ? personal.disposition : item.disposition;
    }
    decisionRevision(member, id) { return this.decisions.get(member)?.get(id)?.revision || 0; }
    pendingItem(i) { return i.important && ['ACTION', 'QUESTION'].includes(i.kind) && !['HIGH_RISK', 'SUSPICIOUS'].includes(this.currentSafety(i)) && i.disposition !== 'accepted'; }
    itemProjection(i, member) {
      return {id: i.id, source: i.source, title: i.title, kind: i.kind, category: i.category,
        summary: i.summary, uncertainty: i.uncertainty, step: i.step, due: i.due,
        safety: this.currentSafety(i), generation: i.generation, disposition: this.decision(member, i),
        review: i.review, merchant: i.merchant, coupon: i.coupon, expiry: i.expiry,
        eligibility: i.eligibility, preference: i.preference, suspiciousText: i.suspiciousText};
    }
    projection(member, {view = 'home', query = '', category = 'all', assignee = 'all', page = 0, offersIntent = false, pendingBucket = 'active'} = {}) {
      if (!this.member(member) || !VIEWS.includes(view) || !['active', 'later', 'archived'].includes(pendingBucket) || typeof query !== 'string' || query.length > 80 || !Number.isInteger(page) || page < 0) throw new Error('Demo view unavailable');
      const permitted = this.visibleItems(member);
      const tasks = this.visibleTasks(member).map(t => this.taskProjection(t));
      const unresolved = permitted.filter(i => this.pendingItem(i));
      const bucket = i => this.decision(member, i) === 'deferred' ? 'later' : this.decision(member, i) === 'archived' ? 'archived' : 'active';
      const pendingCounts = Object.fromEntries(['active', 'later', 'archived'].map(b => [b, unresolved.filter(i => bucket(i) === b).length]));
      const pending = unresolved.filter(i => bucket(i) === (view === 'pending' ? pendingBucket : 'active')).map(i => this.itemProjection(i, member));
      const security = permitted.filter(i => !this.safe(i)).map(i => this.itemProjection(i, member));
      const information = permitted.filter(i => this.safe(i) && i.kind === 'INFO').map(i => this.itemProjection(i, member));
      const offers = offersIntent === true ? permitted.filter(i => this.safe(i) && i.kind === 'PROMOTION').map(i => this.itemProjection(i, member)) : [];
      const events = this.state.events.filter(e => this.canRead(member, e.source)).map(e => ({...e, dateType: 'Confirmed calendar fact'}));
      const upcoming = [...events, ...tasks.filter(t => t.due && t.status !== 'completed').map(t => ({...t, date: t.due, dateType: 'Published task date', task: true}))].sort((a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id));
      const all = {tasks, pending, security, information, offers, upcoming};
      const q = query.trim().toLowerCase();
      const matches = r => (!q || [r.title, r.step, r.summary, r.merchant, r.category].filter(Boolean).join(' ').toLowerCase().includes(q)) && (category === 'all' || r.category === category) && (!['tasks', 'home'].includes(view) || assignee === 'all' || r.assignee === member || r.assignee === 'both' || !r.assignee);
      const filtered = Object.fromEntries(Object.entries(all).map(([k, values]) => [k, values.filter(matches)]));
      const pendingPages = Math.max(1, Math.ceil(filtered.pending.length / PAGE_SIZE));
      const currentPage = Math.min(page, pendingPages - 1);
      return {view, tasks: filtered.tasks, pending: filtered.pending.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE),
        pendingTotal: filtered.pending.length, pendingPages, page: currentPage, security: filtered.security,
        information: filtered.information, offers: filtered.offers, upcoming: filtered.upcoming,
        counts: {tasks: tasks.filter(t => t.status !== 'completed').length, completed: tasks.filter(t => t.status === 'completed').length,
          pending: pendingCounts.active, security: security.length, upcoming: upcoming.length}, pendingCounts, pendingBucket,
        categories: [...new Set(Object.values(all).flat().map(r => r.category))].sort(), offersIntent: offersIntent === true};
    }
    detail(member, kind, id) {
      if (kind === 'task') {
        const t = this.visibleTasks(member).find(t => t.id === id);
        if (!t) return null;
        return {...this.taskProjection(t), evidence: t.evidence.map(id => this.visibleItems(member).find(i => i.id === id)).filter(Boolean).map(i => this.itemProjection(i, member)),
          history: structuredClone(t.history), evidenceChanged: t.evidence.some(id => {
            const i = this.visibleItems(member).find(i => i.id === id);
            return i && i.generation !== (t.evidenceVersions?.[id] || 1);
          }), canEdit: t.editors.includes(member), assignees: [...t.readers.filter(p => this.member(p)), ...(t.readers.length === 2 ? ['both'] : [])]};
      }
      const i = this.visibleItems(member).find(i => i.id === id);
      if (!i) return null;
      const source = this.source(i.source);
      return {...this.itemProjection(i, member), history: structuredClone((this.itemHistory.get(i.id) || []).filter(h => !h.audience || h.audience === member)),
        canTriage: source.reviewers.includes(member) && this.pendingItem(i) && this.decision(member, i) !== 'archived',
        canReopen: source.reviewers.includes(member) && this.pendingItem(i) && this.safe(i) && this.decision(member, i) === 'archived',
        canReview: source.reviewers.includes(member), canAccept: this.decision(member, i) !== 'archived' && this.safe(i) && i.kind === 'ACTION' && i.supported === true && source.acceptors.includes(member) && i.disposition !== 'accepted'};
    }
    sources(member) {
      return this.state.sources.filter(s => this.canRead(member, s.id)).map(s => ({id: s.id, title: s.title, readers: [...s.readers], revision: s.revision, canManage: s.controllers.includes(member)}));
    }
    prepare(member, type, id, extra = null) {
      if (!this.member(member)) return null;
      let record, permission;
      if (['task-status', 'task-assignee'].includes(type)) {
        record = this.visibleTasks(member).find(t => t.id === id && t.editors.includes(member)); permission = record?.revision;
        if (type === 'task-status' && !['pending', 'completed'].includes(extra)) return null;
        if (type === 'task-assignee' && !(typeof extra === 'string' && record && (record.readers.includes(extra) && this.member(extra) || extra === 'both' && record.readers.length === 2))) return null;
      } else if (type === 'sharing') {
        record = this.state.sources.find(s => s.id === id && this.canRead(member, s.id) && s.controllers.includes(member)); permission = record?.revision;
        if (!extra || !this.member(extra.recipient) || extra.recipient === member || typeof extra.allowed !== 'boolean') return null;
      } else if (['accept', 'review', 'defer', 'needs-info', 'archive', 'reopen', 'evidence-change'].includes(type)) {
        record = this.visibleItems(member).find(i => i.id === id); permission = record ? this.source(record.source).revision : null;
        if (!record || !this.source(record.source).reviewers.includes(member)) return null;
        if (type === 'accept' && !this.detail(member, 'item', id).canAccept) return null;
        if (['defer', 'needs-info', 'archive'].includes(type) && !this.detail(member, 'item', id).canTriage) return null;
        if (type === 'reopen' && !this.detail(member, 'item', id).canReopen) return null;
        if (type === 'evidence-change' && !this.source(record.source).controllers.includes(member)) return null;
      } else return null;
      if (!record) return null;
      // Acceptance checks this actor's triage too, but never a peer's private version.
      const decisionRevision = PERSONAL.includes(type) || type === 'accept' ? this.decisionRevision(member, id) : undefined;
      const receipt = Object.freeze({member, type, id, revision: record.revision, generation: record.generation, permission, decisionRevision, extra: extra && typeof extra === 'object' ? Object.freeze(structuredClone(extra)) : extra});
      this.receipts.set(receipt, false); return receipt;
    }
    cancel(receipt) { this.receipts.delete(receipt); return {outcome: 'CANCELED'}; }
    save(receipt, member, confirmed = false) {
      if (confirmed !== true) return this.cancel(receipt);
      if (!this.receipts.has(receipt) || receipt.member !== member) return {outcome: 'DENIED'};
      const current = ['task-status', 'task-assignee'].includes(receipt.type) ? this.visibleTasks(member).find(t => t.id === receipt.id && t.editors.includes(member)) : receipt.type === 'sharing' ? this.state.sources.find(s => s.id === receipt.id && this.canRead(member, s.id) && s.controllers.includes(member)) : this.visibleItems(member).find(i => i.id === receipt.id && this.source(i.source).reviewers.includes(member));
      if (!current) return {outcome: 'DENIED'};
      if (this.receipts.get(receipt)) return {outcome: 'REPLAY'};
      const permission = ['task-status', 'task-assignee'].includes(receipt.type) || receipt.type === 'sharing' ? current.revision : this.source(current.source).revision;
      if (current.revision !== receipt.revision || current.generation !== receipt.generation || permission !== receipt.permission) return {outcome: 'STALE'};
      if (receipt.decisionRevision !== undefined && this.decisionRevision(member, receipt.id) !== receipt.decisionRevision) return {outcome: 'STALE'};
      const fresh = this.prepare(member, receipt.type, receipt.id, receipt.extra);
      if (!fresh) return {outcome: 'DENIED'};
      this.cancel(fresh);
      if (fresh.revision !== receipt.revision || fresh.generation !== receipt.generation || fresh.permission !== receipt.permission || fresh.decisionRevision !== receipt.decisionRevision) return {outcome: 'STALE'};
      const record = ['task-status', 'task-assignee'].includes(receipt.type) ? this.state.tasks.find(t => t.id === receipt.id) : receipt.type === 'sharing' ? this.source(receipt.id) : this.state.items.find(i => i.id === receipt.id);
      const personal = PERSONAL.includes(receipt.type);
      if (receipt.type === 'sharing') {
        const {recipient, allowed} = receipt.extra;
        record.readers = record.readers.filter(p => p !== recipient);
        if (allowed) record.readers.push(recipient);
      } else if (['task-status', 'task-assignee'].includes(receipt.type)) {
        if (receipt.type === 'task-status') record.status = receipt.extra;
        else record.assignee = receipt.extra;
        record.history.push({action: receipt.type === 'task-status' ? `Simulated tracking: ${receipt.extra}` : `Simulated assignment: ${receipt.extra}`, actor: this.state.members[member], revision: record.revision + 1});
      } else {
        const history = this.itemHistory.get(record.id) || [];
        history.push({action: receipt.type, actor: this.state.members[member], generation: record.generation, revision: personal ? receipt.decisionRevision + 1 : record.revision + 1, ...(personal ? {audience: member} : {})});
        this.itemHistory.set(record.id, history);
        if (receipt.type === 'accept') {
          const id = `accepted-${record.id}`;
          if (!this.state.tasks.some(t => t.id === id)) this.state.tasks.push({id, title: record.step, step: record.step, category: record.category, assignee: record.publishTo.length === 1 ? record.publishTo[0] : 'both', due: record.due || null,
            readers: [...record.publishTo], editors: [...record.publishTo], evidence: [record.id], evidenceVersions: {[record.id]: record.generation}, status: 'pending', revision: 1, authority: 'explicitly-accepted', history: [{action: 'Simulated acceptance', actor: this.state.members[member], generation: record.generation}]});
          record.disposition = 'accepted';
        } else if (receipt.type === 'review') record.review = 'confirmed';
        else if (receipt.type === 'evidence-change') { record.generation += 1; record.safetyGeneration = 0; record.disposition = 'pending'; }
        else {
          if (!this.decisions.has(member)) this.decisions.set(member, new Map());
          this.decisions.get(member).set(record.id, {revision: receipt.decisionRevision + 1, generation: record.generation, disposition: ({defer: 'deferred', 'needs-info': 'needs-more-information', archive: 'archived', reopen: 'pending'})[receipt.type]});
        }
      }
      // Private triage must not mutate a shared version or reveal itself via peer CAS.
      if (!personal) record.revision += 1;
      this.receipts.set(receipt, true);
      return {outcome: receipt.type === 'accept' ? 'ACCEPTED' : 'CONFIRMED'};
    }
  }
  const api = {Workbench, VIEWS, PAGE_SIZE, DAY: data.DAY};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.FamilyH0Model = api;
})(globalThis);
