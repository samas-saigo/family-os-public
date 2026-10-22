'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
globalThis.SamasTaskContract=require('../../prototypes/i3-workbench/contract.js');
const {taskParse}=require('../../prototypes/i4b-workbench/editing.js');
const canonical=v=>Array.isArray(v)?'['+v.map(canonical).join(',')+']':v&&typeof v==='object'?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}':JSON.stringify(v);
const page=()=>({schema:'i4b-task-page-v2',synthetic_only:true,pagination:{limit:12,offset:0},query:{responsibility:'mine',step:null},tasks:{items:[],total:0,has_more:false}});
const expected={responsibility:'mine',step:null};
test('bound enum/step/offset, strict whitelists and v1 compatibility',()=>{
  assert.equal(taskParse(canonical(page()),12,0,expected).tasks.total,0);
  const v1=page();delete v1.query;v1.schema='i4b-task-page-v1';assert.equal(taskParse(canonical(v1),12,0).tasks.total,0);
  assert.throws(()=>taskParse(canonical(v1),12,0,expected));assert.throws(()=>taskParse(canonical(page()),12,0));
  for(const change of [v=>v.query.responsibility='other',v=>v.query.step='home-visit',v=>v.query.person_id='i2-clara',v=>delete v.query.step,
    v=>v.extra=true,v=>v.pagination.offset=12,v=>v.tasks.total=1,v=>v.tasks.has_more=true,v=>v.query=null]){
    const v=page();change(v);assert.throws(()=>taskParse(canonical(v),12,0,expected));
  }
  const v=page();v.schema='i4b-task-page-v1';assert.throws(()=>taskParse(canonical(v),12,0));
});
