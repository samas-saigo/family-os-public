'use strict';
const assert=require('node:assert/strict');
global.SamasTaskContract=require('../../prototypes/i3-workbench/contract.js');
global.SamasAcceptance=require('../../prototypes/i4a-workbench/acceptance.js');
global.SamasEditing=require('../../prototypes/i4b-workbench/editing.js');
const old=require('../../prototypes/i7-workbench/reviews.js'),r=require('../../prototypes/i8-workbench/personal.js');
function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
let checks=0;
const row={id:'i8-fiction',revision:1,step:'school-session',supported_date:null,can_accept:true,can_review:true,can_resume:false,reviewed:false,disposition:'active'};
const value={schema:'i8-personal-pending-page-v1',synthetic_only:true,query:{state:'all',step:null},pagination:{limit:12,offset:0},pending:{items:[row],total:1,has_more:false}};
assert.deepEqual(r.parse(canonical(value),12,0),value);checks++;
for(const change of [v=>v.query.state='not-applicable',v=>v.query.actor='i2-devon',v=>v.pending.items[0].can_resume=true,v=>v.pending.items[0].disposition='archived',v=>v.pending.items[0].reason='private',v=>v.pending.items[0].reviewed=1,v=>v.synthetic_only=false,v=>v.schema='i7-personal-pending-page-v1']){const v=structuredClone(value);change(v);assert.throws(()=>r.parse(canonical(v),12,0));checks++;}
for(const state of ['deferred','needs-information','not-applicable']){const v=structuredClone(value);v.pending.items[0].disposition=state;v.pending.items[0].reviewed=state==='not-applicable';v.pending.items[0].can_resume=true;v.query.state=state;assert.equal(r.parse(canonical(v),12,0,state).pending.items[0].disposition,state);assert.throws(()=>old.parse(canonical(v),12,0));const legacy=structuredClone(v);legacy.schema='i7-personal-pending-page-v1';assert.throws(()=>old.parse(canonical(legacy),12,0));checks+=3;}
for(const op of r.operations){const before={...row,disposition:op==='resume'?'deferred':'active',can_resume:op==='resume'};
 for(const reason of op==='not-applicable'?r.reasons:[null]){const p={schema:'i8-personal-preview-v1',synthetic_only:true,id:row.id,revision:1,operation:op,reason,receipt:'a'.repeat(32),before:{reviewed:false,disposition:before.disposition},after:{reviewed:op==='review'||op==='not-applicable',disposition:op==='review'?before.disposition:op==='defer'?'deferred':op==='resume'?'active':op}};
  assert.equal(r.preview(canonical(p),before,op,reason).operation,op);checks++;
  for(const change of [v=>v.before.reviewed=true,v=>v.after.reviewed=!v.after.reviewed,v=>v.after.disposition='archived',v=>v.reason='private text',v=>v.operation='accept',v=>v.revision=2,v=>v.extra='private']){const v=structuredClone(p);change(v);assert.throws(()=>r.preview(canonical(v),before,op,reason));checks++;}
 }
 const result={schema:'i8-write-result-v1',synthetic_only:true,operation:op,receipt:'a'.repeat(32),outcome:'COMMITTED'};assert.equal(r.result(canonical(result)).operation,op);assert.throws(()=>old.result(canonical(result)));checks+=2;
}
const legacy=structuredClone(value);legacy.schema='i7-personal-pending-page-v1';legacy.pending.items[0].disposition='not-applicable';delete legacy.pending.items[0].can_resume;assert.throws(()=>old.parse(canonical(legacy),12,0));checks++;
assert.equal(r.request(row,'not-applicable',null),null);assert.equal(r.request(row,'not-applicable','private notes'),null);assert.throws(()=>r.request(row,'resume',null));checks+=3;
assert.deepEqual(Object.keys(r.copy['zh-CN']).sort(),Object.keys(r.copy['en-US']).sort());assert.deepEqual(r.reasons,['not-my-responsibility','not-participating','personal-judgment']);checks+=2;
assert.equal(r.copy['zh-CN'].resumeEntry,'恢复处理');assert.equal(r.copy['en-US'].resumeEntry,'Resume handling');checks+=2;
const invalid=structuredClone(value);Object.assign(invalid.pending.items[0],{disposition:'not-applicable',can_resume:true});assert.throws(()=>r.parse(canonical(invalid),12,0));checks++;
console.log(checks+' I8 strict DTO/reason/legacy-client cases passed.');
