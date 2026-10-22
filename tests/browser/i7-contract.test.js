'use strict';
const assert=require('node:assert/strict');
global.SamasTaskContract=require('../../prototypes/i3-workbench/contract.js');
global.SamasAcceptance=require('../../prototypes/i4a-workbench/acceptance.js');
global.SamasEditing=require('../../prototypes/i4b-workbench/editing.js');
const r=require('../../prototypes/i7-workbench/reviews.js');
function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
const row={id:'i7-fiction',revision:1,step:'school-session',supported_date:null,can_accept:false,can_review:true,reviewed:false,disposition:'active'};
const value={schema:'i7-personal-pending-page-v1',synthetic_only:true,query:{state:'all',step:null},pagination:{limit:12,offset:0},pending:{items:[row],total:1,has_more:false}};
assert.deepEqual(r.parse(canonical(value),12,0),value);let checks=1;
for(const change of [v=>v.query.state='deferred',v=>v.query.step='home-visit',v=>v.query.actor='i2-devon',v=>v.pending.total=2,v=>v.pending.items[0].can_review=1,v=>v.pending.items[0].disposition='archived',v=>v.pending.items[0].private='hidden',v=>v.pending.items[0].reviewed=null,v=>v.synthetic_only=false,v=>v.schema='i4a-pending-page-v1']){const v=structuredClone(value);change(v);assert.throws(()=>r.parse(canonical(v),12,0));checks++;}
for(const state of ['viewed','deferred','needs-information']){assert.throws(()=>r.parse(canonical({...value,query:{state,step:null}}),12,0,state));checks++;}
for(const op of r.operations){const p={schema:'i7-personal-preview-v1',synthetic_only:true,id:row.id,revision:1,operation:op,receipt:'a'.repeat(32)};assert.equal(r.preview(canonical(p),row,op).operation,op);assert.throws(()=>r.preview(canonical({...p,revision:2}),row,op));assert.throws(()=>r.preview(canonical({...p,operation:'accept'}),row,op));checks+=3;}
for(const op of [null,'accept','edit',...r.operations]){const v={schema:'i7-write-result-v1',synthetic_only:true,operation:op,receipt:op?'a'.repeat(32):null,outcome:op?'COMMITTED':'NOT_APPLIED-verified-absence'};assert.equal(r.result(canonical(v)).operation,op);checks++;}
assert.throws(()=>r.result(canonical({schema:'i7-write-result-v1',synthetic_only:true,operation:'archive',receipt:'a'.repeat(32),outcome:'COMMITTED'})));checks++;
assert.deepEqual(Object.keys(r.copy['zh-CN']).sort(),Object.keys(r.copy['en-US']).sort());
assert.match(r.stateLabel('zh-CN',{reviewed:true,disposition:'deferred'}),/我已查看.*我已暂缓/);
console.log(checks+' I7 strict contract cases and bilingual/independent-state checks passed.');
