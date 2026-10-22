'use strict';
const {test}=require('node:test'), assert=require('node:assert/strict');
const {Workbench}=require('../../prototypes/h0-workbench/model.js');
const p=require('../../prototypes/h0-workbench/presentation.js');
const apply=(m,who,op,id='workshop')=>m.save(m.prepare(who,op,id),who,true);
const list=(m,who,b='active',page=0)=>m.projection(who,{view:'pending',pendingBucket:b,page});
const snapshot=m=>structuredClone([m.state,m.decisions,m.itemHistory]);
test('archive removes primary without deleting evidence or creating tasks',()=>{
 const m=new Workbench(),before=m.state.tasks.length, item=structuredClone(m.state.items[0]);
 assert.equal(apply(m,'nora','archive').outcome,'CONFIRMED');
 assert.equal(list(m,'nora').pendingTotal,7);assert.equal(list(m,'nora','archived').pending[0].id,'workshop');
 assert.equal(m.state.tasks.length,before);assert.equal(m.state.items.length,20);
 assert.equal(m.detail('nora','item','workshop').history.at(-1).actor,'Nora');
 assert.equal(m.state.items[0].summary,item.summary);
});
test('defer remains retrievable in same-page later category',()=>{
 const m=new Workbench();apply(m,'nora','defer','visit');
 assert.equal(list(m,'nora').pendingTotal,7);assert.equal(list(m,'nora','later').pending[0].id,'visit');
 assert.equal(p.project(m,'nora','zh-CN',{view:'pending',pendingBucket:'later',query:'维修'}).pendingTotal,1);
 assert.equal(m.projection('nora').counts.pending,7);
});
test('details and category browsing never change decisions',()=>{
 const m=new Workbench();apply(m,'nora','archive');const before=snapshot(m);
 for(const who of ['nora','julian'])for(const b of ['active','later','archived']) {list(m,who,b);p.detail(m,who,'zh-CN','item','workshop');}
 assert.deepEqual(snapshot(m),before);
});
test('acceptance is one shared task with exact replay protection',()=>{
 const m=new Workbench(),r=m.prepare('nora','accept','workshop');
 assert.equal(m.save(r,'nora',true).outcome,'ACCEPTED');assert.equal(m.save(r,'nora',true).outcome,'REPLAY');
 assert.equal(m.prepare('julian','accept','workshop'),null);
 assert.equal(m.state.tasks.filter(t=>t.id==='accepted-workshop').length,1);
 for(const who of ['nora','julian'])assert.equal(list(m,who).pendingTotal,7);
});
test('personal archive never decides or publishes personal history for peer',()=>{
 const m=new Workbench();apply(m,'nora','archive');
 assert.equal(list(m,'julian').pendingTotal,8);assert.equal(list(m,'julian','archived').pendingTotal,0);
 assert.equal(m.detail('julian','item','workshop').history.length,0);
 assert.equal(m.prepare('julian','reopen','workshop'),null);
 assert.equal(apply(m,'julian','archive').outcome,'CONFIRMED');
 assert.equal(m.detail('julian','item','workshop').history.at(-1).actor,'Julian');
});
test('original actor can explicitly reopen only current archive',()=>{
 const m=new Workbench();apply(m,'nora','archive');const r=m.prepare('nora','reopen','workshop');assert.ok(r);
 assert.equal(m.save(r,'nora',true).outcome,'CONFIRMED');assert.equal(m.save(r,'nora',true).outcome,'REPLAY');
 assert.equal(list(m,'nora','archived').pendingTotal,0);assert.equal(list(m,'nora').pendingTotal,8);
 assert.equal(m.state.tasks.length,5);
});
test('source revocation hides archives counts search and history before replay',()=>{
 const m=new Workbench();const r=m.prepare('julian','archive','workshop');m.save(r,'julian',true);
 const reopen=m.prepare('julian','reopen','workshop');m.save(m.prepare('nora','sharing','notices',{recipient:'julian',allowed:false}),'nora',true);
 assert.equal(list(m,'julian','archived').pendingTotal,0);assert.equal(m.detail('julian','item','workshop'),null);
 assert.equal(m.save(r,'julian',true).outcome,'DENIED');assert.equal(m.save(reopen,'julian',true).outcome,'DENIED');
 assert.equal(p.project(m,'julian','zh-CN',{view:'pending',pendingBucket:'archived',query:'工作坊'}).pendingTotal,0);
});
test('cancel or unconfirmed triage never changes history or state',()=>{
 const m=new Workbench();for(const op of ['archive','defer'])for(const confirmed of [false,undefined,1,'true']){
 const before=snapshot(m),r=m.prepare('nora',op,'workshop');assert.equal(m.save(r,'nora',confirmed).outcome,'CANCELED');assert.deepEqual(snapshot(m),before);}
 apply(m,'nora','archive');const before=snapshot(m),r=m.prepare('nora','reopen','workshop');m.cancel(r);assert.equal(m.save(r,'nora',true).outcome,'DENIED');assert.deepEqual(snapshot(m),before);
});
test('stale triage loses CAS without partial effects',()=>{
 const m=new Workbench(),a=m.prepare('nora','archive','workshop'),b=m.prepare('nora','defer','workshop');
 m.save(b,'nora',true);const before=snapshot(m);assert.equal(m.save(a,'nora',true).outcome,'STALE');assert.deepEqual(snapshot(m),before);
});
test('exact archive replay appends only one actual-actor event',()=>{
 const m=new Workbench(),r=m.prepare('nora','archive','workshop');m.save(r,'nora',true);const before=snapshot(m);
 assert.equal(m.save(r,'nora',true).outcome,'REPLAY');assert.deepEqual(snapshot(m),before);assert.equal(m.itemHistory.get('workshop').length,1);
 assert.equal(m.save({...r},'nora',true).outcome,'DENIED');assert.equal(m.save(r,'julian',true).outcome,'DENIED');
});
test('needs-information stays unresolved not archived or accepted',()=>{
 const m=new Workbench();apply(m,'nora','needs-info','visit');assert.equal(list(m,'nora').pendingTotal,8);
 assert.equal(m.detail('nora','item','visit').disposition,'needs-more-information');assert.equal(list(m,'nora','archived').pendingTotal,0);
 assert.equal(m.state.tasks.length,5);
});
test('evidence changes and apparent reverts invalidate archived binding',()=>{
 const m=new Workbench();apply(m,'nora','archive');const r=m.prepare('nora','reopen','workshop');apply(m,'nora','evidence-change');
 assert.equal(m.save(r,'nora',true).outcome,'STALE');assert.equal(m.prepare('nora','reopen','workshop'),null);
 assert.equal(list(m,'nora','archived').pendingTotal,0);assert.equal(list(m,'nora').pendingTotal,8);
 const i=m.state.items.find(i=>i.id==='workshop');i.generation++;assert.equal(m.prepare('nora','accept','workshop'),null);
 assert.equal(m.detail('nora','item','workshop').history.length,2);
});
test('safety and reviewer authority gate reopening without clearance',()=>{
 const m=new Workbench();apply(m,'nora','archive');const i=m.state.items.find(i=>i.id==='workshop');
 for(const risk of ['UNKNOWN','SUSPICIOUS','HIGH_RISK']){i.safety=risk;assert.equal(m.prepare('nora','reopen','workshop'),null);}
 i.safety='CLEAR';m.source(i.source).reviewers=['julian'];assert.equal(m.prepare('nora','reopen','workshop'),null);
 assert.equal(m.prepare('nora','accept','workshop'),null);
});
test('category pagination totals are access-first deterministic and complete',()=>{
 const m=new Workbench();for(const id of ['workshop','visit','clinic-question','rail'])apply(m,'nora','archive',id);
 const first=list(m,'nora','archived'), ids=[];assert.equal(first.pendingTotal,4);assert.equal(first.pendingPages,2);
 for(let n=0;n<first.pendingPages;n++)ids.push(...list(m,'nora','archived',n).pending.map(i=>i.id));assert.equal(new Set(ids).size,4);
 const before=list(m,'julian','archived');const hidden=m.state.items.find(i=>i.id==='nora-class');
 for(let n=0;n<100;n++)m.state.items.push({...hidden,id:'hidden-'+n});assert.deepEqual(list(m,'julian','archived'),before);
 assert.throws(()=>list(m,'nora','invalid'));
});
test('promotions and accepted tasks never gain triage obligations',()=>{
 const m=new Workbench();for(const id of ['garden-offer','expired-offer','promo-risk','promo-unknown','login-risk'])for(const op of ['archive','defer','reopen','needs-info'])assert.equal(m.prepare('nora',op,id),null);
 apply(m,'nora','accept');for(const op of ['archive','defer','needs-info','reopen'])assert.equal(m.prepare('nora',op,'workshop'),null);
 assert.equal(list(m,'nora').pendingTotal,7);
});
test('all cross-peer personal operations interleave without changing peer output or CAS',()=>{
 for(const left of ['archive','defer','needs-info','reopen'])for(const right of ['archive','defer','needs-info','reopen'])for(const first of ['nora','julian']){
  const m=new Workbench();if(left==='reopen')apply(m,'nora','archive');if(right==='reopen')apply(m,'julian','archive');
  const a=m.prepare('nora',left,'workshop'),b=m.prepare('julian',right,'workshop');assert.ok(a&&b);
  const second=first==='nora'?'julian':'nora',tokens={nora:a,julian:b};
  const before=[m.projection(second),m.detail(second,'item','workshop')],shared=m.state.items.find(i=>i.id==='workshop').revision;
  assert.equal(m.save(tokens[first],first,true).outcome,'CONFIRMED');
  assert.deepEqual([m.projection(second),m.detail(second,'item','workshop')],before);
  assert.equal(m.save(tokens[second],second,true).outcome,'CONFIRMED');assert.equal(m.state.items.find(i=>i.id==='workshop').revision,shared);
  for(const who of ['nora','julian'])assert.equal(m.detail(who,'item','workshop').history.at(-1).actor,m.state.members[who]);
 }
});
test('peer archive does not invalidate prepared shared acceptance or create another task',()=>{
 for(const [archiver,acceptor] of [['nora','julian'],['julian','nora']]){
  const m=new Workbench(),a=m.prepare(archiver,'archive','workshop'),b=m.prepare(acceptor,'accept','workshop');
  assert.equal(m.save(a,archiver,true).outcome,'CONFIRMED');assert.equal(m.save(b,acceptor,true).outcome,'ACCEPTED');
  assert.equal(m.save(b,acceptor,true).outcome,'REPLAY');assert.equal(m.state.tasks.filter(t=>t.id==='accepted-workshop').length,1);
  assert.equal(m.detail(acceptor,'task','accepted-workshop').history[0].actor,m.state.members[acceptor]);
  assert.equal(list(m,archiver,'archived').pendingTotal,0);assert.equal(list(m,acceptor).pendingTotal,7);
 }
});
test('same-actor personal changes stale every earlier personal command',()=>{
 for(const op of ['archive','defer','needs-info','reopen']){
  const m=new Workbench();if(op==='reopen')apply(m,'nora','archive');
  const a=m.prepare('nora',op,'workshop'),b=m.prepare('nora',op,'workshop');assert.ok(a&&b);
  assert.equal(m.save(a,'nora',true).outcome,'CONFIRMED');const before=snapshot(m);
  assert.equal(m.save(b,'nora',true).outcome,'STALE');assert.deepEqual(snapshot(m),before);
  assert.equal(m.save(a,'nora',true).outcome,'REPLAY');assert.deepEqual(snapshot(m),before);
 }
});
test('same-actor triage invalidates prepared acceptance without revoking peer authority',()=>{
 const m=new Workbench(),own=m.prepare('nora','accept','workshop'),peer=m.prepare('julian','accept','workshop');apply(m,'nora','archive');
 const before=snapshot(m);assert.equal(m.save(own,'nora',true).outcome,'STALE');assert.deepEqual(snapshot(m),before);
 assert.equal(m.save(peer,'julian',true).outcome,'ACCEPTED');assert.equal(m.state.tasks.filter(t=>t.id==='accepted-workshop').length,1);
});
test('personal version remains monotonic through archive and reopen without ABA',()=>{
 const m=new Workbench(),old=m.prepare('nora','archive','workshop');apply(m,'nora','archive');apply(m,'nora','reopen');
 assert.equal(m.decisionRevision('nora','workshop'),2);const before=snapshot(m);
 assert.equal(m.save(old,'nora',true).outcome,'STALE');assert.deepEqual(snapshot(m),before);
 apply(m,'nora','archive');assert.equal(m.decisionRevision('nora','workshop'),3);
 assert.deepEqual(m.detail('nora','item','workshop').history.map(h=>h.revision),[1,2,3]);assert.equal(m.detail('julian','item','workshop').history.length,0);
});
test('shared acceptance stales pending personal receipts while exact historical replay is harmless',()=>{
 const m=new Workbench(),archive=m.prepare('nora','archive','workshop'),later=m.prepare('julian','defer','workshop');
 const accepted=m.prepare('julian','accept','workshop');assert.equal(m.save(accepted,'julian',true).outcome,'ACCEPTED');const before=snapshot(m);
 for(const [r,who] of [[archive,'nora'],[later,'julian']])assert.equal(m.save(r,who,true).outcome,'STALE');
 assert.deepEqual(snapshot(m),before);assert.equal(m.prepare('nora','archive','workshop'),null);
});
test('independent personal versions still bind shared evidence and current source permissions',()=>{
 for(const change of ['evidence','permission']){
  const m=new Workbench(),a=m.prepare('nora','archive','workshop'),b=m.prepare('julian','defer','workshop');
  if(change==='evidence')apply(m,'nora','evidence-change');
  else m.save(m.prepare('nora','sharing','notices',{recipient:'julian',allowed:false}),'nora',true);
  const before=snapshot(m);assert.equal(m.save(a,'nora',true).outcome,'STALE');
  assert.equal(m.save(b,'julian',true).outcome,change==='evidence'?'STALE':'DENIED');assert.deepEqual(snapshot(m),before);
 }
});
test('cancelled private receipts do not bump either version or invalidate peers',()=>{
 const m=new Workbench(),own=m.prepare('nora','archive','workshop'),peer=m.prepare('julian','archive','workshop'),before=snapshot(m);
 assert.equal(m.save(own,'nora',false).outcome,'CANCELED');assert.deepEqual(snapshot(m),before);
 assert.equal(m.save(own,'nora',true).outcome,'DENIED');assert.equal(m.save(peer,'julian',true).outcome,'CONFIRMED');
 assert.equal(m.save(peer,'nora',true).outcome,'DENIED');const after=snapshot(m);
 assert.equal(m.save(peer,'julian',true).outcome,'REPLAY');assert.deepEqual(snapshot(m),after);
});
