'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {specimens,copy}=require('../../prototypes/ux2-design-preview/preview.js');
test('both languages cover the same nonempty design vocabulary',()=>{
  assert.deepEqual(Object.keys(copy['zh-CN']).sort(),Object.keys(copy['en-US']).sort());
  for(const strings of Object.values(copy))for(const value of Object.values(strings))assert(typeof value==='string'&&value.trim());
});
test('specimens are deeply immutable, not a new task lifecycle',()=>{
  assert(Object.isFrozen(specimens.tasks[0]));assert.throws(()=>{specimens.tasks[0].assignee='devon';},TypeError);
  assert.throws(()=>specimens.tasks.push({}),TypeError);assert.deepEqual(specimens.tasks.map(t=>t.assignee),['clara','devon','joint']);
});
test('unknown dates stay absent and the declared date stays fixed',()=>{
  assert.equal(specimens.tasks.filter(t=>t.date===null).length,2);
  assert.deepEqual(specimens.tasks.filter(t=>t.date).map(t=>t.date),['2035-06-12']);
});
test('undecided, information-needed and deferred specimens remain distinct',()=>{
  assert.deepEqual(specimens.pending.map(p=>p.state),['decision','information','later']);
  assert(specimens.pending.every(p=>!Object.hasOwn(p,'task_id')));
});
test('each specimen references translated visible text, not private source payload',()=>{
  for(const t of specimens.tasks){assert(copy['zh-CN'][t.title]);assert.deepEqual(Object.keys(t).sort(),['assignee','date','id','status','title']);}
  for(const p of specimens.pending){assert(copy['en-US'][p.title]);assert(copy['en-US'][p.description]);}
});
test('copy describes no-save confirmation and uncertainty in both languages',()=>{
  assert.match(copy['zh-CN'].notSaved,/没有保存/);assert.match(copy['en-US'].notSaved,/No edit saved/);
  assert.match(copy['zh-CN'].unknownBody,/不自动重发/);assert.match(copy['en-US'].unknownBody,/without blind retries/);
});
