'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const rows = require('../../prototypes/h0-workbench/translations.js');
const i = require('../../prototypes/h0-workbench/i18n.js');
const p = require('../../prototypes/h0-workbench/presentation.js');
const {Workbench} = require('../../prototypes/h0-workbench/model.js');
const seed = require('../../prototypes/h0-workbench/fixtures.js').seed;
const fresh = () => new Workbench();
const apply = (m, member, type, id, extra = null) => m.save(m.prepare(member, type, id, extra), member, true);

test('complete bilingual keys and matching placeholders with no duplicate entries', () => {
  assert.equal(rows.length, 341);
  assert.deepEqual(Object.keys(i.dictionaries['zh-CN']), Object.keys(i.dictionaries['en-US']));
  assert.equal(new Set(rows.map(r => r[0])).size, rows.length);
  for (const [key,en,zh] of rows) {
    assert.deepEqual(i.parameters(en), i.parameters(zh), key);
    if (key !== 'chrome.brand') assert.match(zh, /[\u3400-\u9fff]/u, key); else assert.equal(zh, 'Samas');
  }
});
test('dictionary compiler rejects duplicate keys and malformed entries', () => {
  for (const entries of [[['key','English','中文'],['key','Other','其他']], [['key','English']], [['key',null,'中文']], [['','English','中文']], [['key','English','']]]) assert.throws(() => i.compile(entries), /Presentation unavailable/);
});
test('placeholder mismatches and malformed braces fail closed', () => {
  for (const entries of [[['key','{actor}','{recipient}']], [['key','{actor} {actor}','{actor}']], [['key','bad { syntax','中文']]]) assert.throws(() => i.compile(entries));
});
test('unknown keys/locales and wrong interpolation parameters fail closed', () => {
  for (const fn of [() => i.t('en-US','unknown'), () => i.t('other','ui.home'), () => i.t('zh-CN','format.search'), () => i.t('zh-CN','format.search',{query:'ok',extra:'bad'}), () => i.t('zh-CN','format.search',{query:{}}), () => i.t('zh-CN','format.search',{query:Infinity})]) assert.throws(fn, /Presentation unavailable/);
});
test('safe interpolation returns literal text including markup and dollar sequences', () => {
  const query='<img src=x onerror=alert(1)> $& ${secret}';
  assert.ok(i.t('zh-CN','format.search',{query}).includes(query));
});
test('fresh preferences default both peers to Chinese with independent memory', () => {
  const prefs=new i.Preferences(); assert.equal(prefs.get('nora'),'zh-CN'); assert.equal(prefs.get('julian'),'zh-CN');
  prefs.set('nora','en-US'); assert.equal(prefs.get('julian'),'zh-CN'); assert.equal(prefs.get('nora'),'en-US'); prefs.reset(); assert.equal(prefs.get('nora'),'zh-CN');
});
test('fabricated peers and invalid locales cannot establish preferences', () => {
  const prefs=new i.Preferences(); for (const member of ['__proto__','other',['nora'],{member:'nora'}]) assert.throws(() => prefs.get(member)); assert.throws(() => prefs.set('nora','en'));
});
test('all fictional fields have authored translations without changing business identity', () => {
  const s=seed(); for (const [collection,kind] of [['sources','source'],['items','item'],['tasks','task'],['events','event']]) for (const row of s[collection]) {
    for (const locale of i.LOCALES) {const display=p.record(locale,row,kind); assert.equal(display.id,row.id); assert.equal(display.generation,row.generation); assert.equal(display.safety,row.safety); assert.equal(display.due,row.due); assert.equal(display.coupon,row.coupon); assert.deepEqual(display.readers,row.readers);}
  }
});
test('every existing view is localized without mutating household state or history', () => {
  const m=fresh(), before=structuredClone(m.state);
  for (const locale of i.LOCALES) for (const view of ['home','tasks','pending','upcoming','security','information','offers']) p.project(m,'nora',locale,{view,offersIntent:true});
  assert.deepEqual(m.state,before); assert.equal(m.itemHistory.size,0);
});
test('Chinese and English keywords retrieve the same authorized task', () => {
  const m=fresh();
  assert.deepEqual(p.project(m,'nora','zh-CN',{view:'tasks',query:'出游包'}).tasks.map(t=>t.id), ['task-bag']);
  assert.deepEqual(p.project(m,'nora','en-US',{view:'tasks',query:'outing bag'}).tasks.map(t=>t.id), ['task-bag']);
  assert.equal(p.project(m,'nora','zh-CN',{view:'tasks',query:'outing bag'}).tasks.length,0);
});
test('Chinese source keywords cannot reveal another peers private source', () => {
  const m=fresh(); assert.equal(p.project(m,'julian','zh-CN',{view:'pending',query:'陶艺'}).pendingTotal,0);
  assert.equal(p.project(m,'nora','zh-CN',{view:'pending',query:'陶艺'}).pendingTotal,1);
  assert.equal(p.detail(m,'julian','zh-CN','item','nora-class'),null);
});
test('hidden population cannot influence translated results, categories, ordering or errors', () => {
  const m=fresh(); for (const locale of i.LOCALES) {
    const before=p.project(m,'julian',locale,{view:'pending',page:1}); const hidden=m.state.items.find(i=>i.id==='nora-class');
    for(let n=0;n<100;n++) m.state.items.push({...hidden,id:`fiction-hidden-${n}`,title:'UNTRANSLATED UNKNOWN',category:'Not a presentation key'});
    assert.deepEqual(p.project(m,'julian',locale,{view:'pending',page:1}),before);
  }
});
test('private evidence changes never affect neutral publication search in either locale', () => {
  const m=fresh(); const before=i.LOCALES.map(locale=>p.project(m,'nora',locale));
  const h=m.state.items.find(r=>r.id==='picnic-note'); h.title='unmapped private text';h.generation++;h.safety='HIGH_RISK';
  i.LOCALES.forEach((locale,n)=>assert.deepEqual(p.project(m,'nora',locale),before[n]));
});
for(const locale of i.LOCALES) {
  test(`${locale}: source revocation removes search/counts, independent task publication survives`, () => {
    const m=fresh(); apply(m,'nora','sharing','notices',{recipient:'julian',allowed:false});
    assert.equal(p.detail(m,'julian',locale,'item','registration'),null);
    assert.equal(p.project(m,'julian',locale,{view:'pending',query:locale==='zh-CN'?'维修':'Repair'}).pendingTotal,0);
    assert.equal(p.detail(m,'julian',locale,'task','task-school').evidence.length,0);
    assert.ok(p.detail(m,'julian',locale,'task','task-school').title);
  });
  test(`${locale}: review never creates a task and separate acceptance does`, () => {
    const m=fresh(), count=m.state.tasks.length;apply(m,'nora','review','workshop');
    assert.equal(m.state.tasks.length,count);apply(m,'nora','accept','workshop');
    assert.equal(m.state.tasks.length,count+1); assert.equal(p.detail(m,'nora',locale,'task','accepted-workshop').title,i.t(locale,'fixture.workshop.step'));
    apply(m,'nora','review','workshop');assert.ok(p.project(m,'nora',locale).tasks.some(t=>t.id==='accepted-workshop'));
  });
  test(`${locale}: unsafe requests and promotions never become accepted tasks or offers`, () => {
    const m=fresh(); for(const id of ['login-risk','payment-risk','promo-risk','promo-unknown','unknown-school']) assert.equal(m.prepare('nora','accept',id),null);
    assert.ok(p.project(m,'nora',locale,{offersIntent:true}).offers.every(r=>r.safety==='CLEAR'));
    assert.ok(p.project(m,'nora',locale).pending.every(r=>r.kind!=='PROMOTION'));
  });
  test(`${locale}: offers require exact explicit intent and retain coupon codes`, () => {
    const m=fresh(); assert.equal(p.project(m,'nora',locale,{view:'offers'}).offers.length,0);
    const offers=p.project(m,'nora',locale,{view:'offers',offersIntent:true}).offers; assert.equal(offers.length,3);
    assert.deepEqual(offers.map(o=>o.coupon),['DEMO15','DEMO-WEEKEND','DEMO-OLD']);
  });
  test(`${locale}: cancellation, stale and replay semantics remain unchanged`, () => {
    const m=fresh();let receipt=m.prepare('nora','accept','workshop');m.cancel(receipt);assert.equal(m.save(receipt,'nora',true).outcome,'DENIED');
    receipt=m.prepare('nora','accept','workshop');apply(m,'nora','evidence-change','workshop');assert.equal(m.save(receipt,'nora',true).outcome,'STALE');assert.equal(p.detail(m,'nora',locale,'item','workshop').safety,'UNKNOWN');
  });
}
test('UTC locale formatting changes presentation only and uses fixed dates', () => {
  const date='2031-04-14'; assert.notEqual(i.date('zh-CN',date,true),i.date('en-US',date,true));
  assert.match(i.date('zh-CN',date,true),/2031/);assert.match(i.date('en-US',date,true),/2031/);
  assert.equal(i.time('zh-CN','10:30'),'10:30');assert.match(i.time('en-US','10:30'),/10:30 AM/);
  assert.equal(i.date('zh-CN',null),i.t('zh-CN','format.unknownDate'));assert.equal(i.number('zh-CN',1000),'1,000');
  const m=fresh(); assert.equal(p.project(m,'nora','zh-CN').upcoming[0].date,p.project(m,'nora','en-US').upcoming[0].date);
});
test('all static chrome keys and literal interface keys are checked', () => {
  const root=path.resolve(__dirname,'../../prototypes/h0-workbench');
  const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
  const app=fs.readFileSync(path.join(root,'app.js'),'utf8');
  for(const match of [...html.matchAll(/data-i18n(?:-label)?="([^"]+)"/g),...app.matchAll(/tr\('([^']+)'/g)]) for(const locale of i.LOCALES) assert.ok(Object.hasOwn(i.dictionaries[locale],match[1]),match[1]);
  assert.ok(!/button\('[A-Za-z][A-Za-z ]+/.test(app));
  assert.ok(!/el\('[^']+', '[A-Za-z][A-Za-z ]+/.test(app));
});
test('Chinese presentation has no English prose except intentional names/identifiers', () => {
  const allowed=new Set(['Samas','Family','OS','H1','JavaScript','Moss','Mug','Lantern','Trails','Old','Leaf']);
  for(const [key,,zh] of rows) for(const word of zh.replace(/\{[A-Za-z]+\}/g,'').match(/[A-Za-z][A-Za-z0-9]*/g)||[]) assert.ok(allowed.has(word),`${key}: ${word}`);
});
test('specific bilingual result messages distinguish committed actions and errors',()=>{
 for(const locale of i.LOCALES){
  const keys=['result.defer','result.archive','result.reopen','result.completed','result.taskReopened'];
  const values=keys.map(k=>i.t(locale,k));assert.equal(new Set(values).size,keys.length);
  for(const key of ['ui.not.saved.evidence.or.permissions.changed','ui.not.saved.this.decision.is.unavailable','ui.already.recorded.no.duplicate.simulated.change'])assert.ok(!values.includes(i.t(locale,key)));
  assert.throws(()=>i.t(locale,'result.assignment'));assert.ok(i.t(locale,'result.assignment',{owner:i.t(locale,'member.julian')}).includes(i.t(locale,'member.julian')));
 }
 assert.equal(i.t('zh-CN','ui.confirmed.a.fictional.step.was.separately'),'已加入家庭待办');
 assert.equal(i.t('zh-CN','result.archive'),'已归档，仅对你生效');
});
test('brand and genuine empty-category copy are explicit without changing identifiers',()=>{
 for(const locale of i.LOCALES){
  assert.ok(i.t(locale,'chrome.title').startsWith('Samas Family OS'));assert.equal(i.t(locale,'chrome.brand'),'Samas');
  const empty=['active','later','archived','tasks','allTasks'].map(k=>i.t(locale,`empty.${k}`));assert.equal(new Set(empty).size,5);
  assert.ok(!empty.includes(i.t(locale,'empty.filtered')));
 }
 assert.equal(p.detail(fresh(),'nora','zh-CN','item','workshop').id,'workshop');
});

test('home count shortcuts separate numbers from natural, bounded bilingual labels',()=>{
 const keys=['ui.accepted.steps.open','ui.unresolved.questions','ui.known.dates','ux.security.count'];
 assert.deepEqual(keys.map(k=>i.t('zh-CN',k)),['待办','待确认','有日期','待核实']);
 for(const locale of i.LOCALES)for(const key of keys)assert.ok(!/[0-9]/.test(i.t(locale,key)));
 for(const locale of i.LOCALES){const notice=i.t(locale,'chrome.notice');assert.ok(notice.includes(locale==='zh-CN'?'虚构数据':'Fictional data'));assert.ok(notice.includes(locale==='zh-CN'?'无真实操作':'No real actions'));}
});

test('action labels never end in literal ellipses and retain separate confirmations',()=>{
 const keys=['pending.archive','pending.reopen','ui.simulate.reopening','ui.simulate.completion','ui.accept.suggested.step','ui.defer.question','ui.needs.more.information','ui.change.the.workshop.evidence.sample','ux.assign'];
 for(const locale of i.LOCALES)for(const key of keys)assert.ok(!/(?:\.\.\.|…)[\s]*$/.test(i.t(locale,key)),key);
 assert.equal(i.t('zh-CN','ux.assign'),'调整分工');assert.equal(i.t('zh-CN','ui.simulate.completion'),'标记完成');
 assert.equal(i.t('zh-CN','format.allPending'),'查看全部');assert.equal(i.t('zh-CN','format.inspectCount'),'查看待核实');
 for(const locale of i.LOCALES)assert.notEqual(i.t(locale,'ui.simulate.completion'),i.t(locale,'ui.confirm.simulated.tracking.change'));
});
