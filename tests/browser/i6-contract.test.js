'use strict';
const assert=require('node:assert/strict');
const c=require('../../prototypes/i6-workbench/explanations.js');
function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
const row={id:'i5_abc',revision:1,step:'school-session',supported_date:'2040-09-18',can_accept:true};
const value={schema:'i6-pending-explanation-v1',synthetic_only:true,...row,generation:1,definition:'i5-fictional-routing-v1-stagea-v2',source_kind:'structured-fictional-input',action:'supported',reasons:['structured-support'],safety:'clear'};
assert.deepEqual(c.parse(canonical(value),row),value);
let n=1;
for(const change of [{private:'forbidden'},{generation:0},{generation:1001},{revision:2},{id:'other'},
 {source_kind:'gmail'},{action:'AI 98%'},{reasons:['unknown']},{reasons:[]},{reasons:['structured-support','structured-support']},
 {safety:'safe forever'},{safety:null},{safety:'high-risk'},{can_accept:false},{definition:'other'},
 {step:'home-visit'},{supported_date:'2040-09-19'},{synthetic_only:false},{schema:'other'}]){
 assert.throws(()=>c.parse(canonical({...value,...change}),row));n++;
}
for(const raw of [JSON.stringify(value),canonical(value)+' ',canonical(value).replace('"generation":1','"generation":1,"generation":1'),'{', 'x'.repeat(4097)]){assert.throws(()=>c.parse(raw,row));n++;}
const blocked={...value,can_accept:false,safety:'unknown',action:'unavailable',reasons:['current-evidence-unavailable']};
assert.equal(c.parse(canonical(blocked),{...row,can_accept:false}).action,'unavailable');n++;
assert.equal(c.parse(canonical({...blocked,safety:null}),{...row,can_accept:false}).safety,null);n++;
for(const change of [{action:'none',reasons:['structured-support']},{action:'supported',reasons:['conflicting-action-evidence']},{action:'none',reasons:['missing-action-step']}]){assert.throws(()=>c.parse(canonical({...value,can_accept:false,...change}),{...row,can_accept:false}));n++;}
assert.deepEqual(Object.keys(c.copy['zh-CN']).sort(),Object.keys(c.copy['en-US']).sort());
for(const locale of Object.keys(c.copy))for(const text of Object.values(c.copy[locale]))assert.equal(typeof text,'string');
console.log(n+' I6 strict contract cases and bilingual parity passed.');
