'use strict';
const assert=require('node:assert/strict');
global.SamasTaskContract=require('../../prototypes/i3-workbench/contract.js');
global.SamasAcceptance=require('../../prototypes/i4a-workbench/acceptance.js');
global.SamasEditing=require('../../prototypes/i4b-workbench/editing.js');
require('../../prototypes/i7-workbench/reviews.js');
require('../../prototypes/i8-workbench/personal.js');
const home=require('../../prototypes/i9-workbench/home.js');
function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
const task={id:'task_'+'a'.repeat(32),step:'school-session',assignee:'joint',status:'pending',approved_date:null,revision:1,can_edit:true};
const pending={id:'i9-question',revision:1,step:null,supported_date:null,can_accept:false,can_review:true,can_resume:false,reviewed:true,disposition:'active'};
const value={schema:'i9-personal-action-home-v1',synthetic_only:true,member:'i2-clara',sections:{mine:{total:1,items:[{item:task,reason:'joint-task'}]},decisions:{total:1,items:[{item:pending,reason:'viewed-undecided'}]},followup:{total:0,items:[]},collaboration:{total:0,items:[]}}};
let checks=0;
assert.equal(home.parse(canonical(value),'i2-clara').home.sections.decisions.total,1);checks++;
const mutations=[v=>v.schema='old',v=>v.synthetic_only=false,v=>v.member='i2-devon',v=>v.person_id='i2-clara',v=>v.sections.mine.total=2,v=>v.sections.mine.total=-1,v=>v.sections.mine.total=true,v=>v.sections.mine.items[0].item.status='completed',v=>v.sections.mine.items[0].item.source='private',v=>v.sections.mine.items[0].reason='other-task',v=>v.sections.decisions.items[0].item.can_review=false,v=>v.sections.decisions.items[0].item.disposition='not-applicable',v=>v.sections.decisions.items[0].reason='undecided',v=>v.sections.collaboration=structuredClone(v.sections.mine),v=>v.sections.decisions.items[0].item.supported_date='2030-02-30',v=>v.sections.decisions.items[0].item.personal_reason='private'];
for(const change of mutations){const v=structuredClone(value);change(v);assert.throws(()=>home.parse(canonical(v),'i2-clara'));checks++;}
for(const reason of ['deferred','needs-information']){const v=structuredClone(value);v.sections.followup=v.sections.decisions;v.sections.decisions={total:0,items:[]};Object.assign(v.sections.followup.items[0].item,{disposition:reason,can_resume:true});v.sections.followup.items[0].reason=reason;assert.equal(home.parse(canonical(v),'i2-clara').home.sections.followup.total,1);checks++;}
const dates=structuredClone(value);dates.sections.mine={total:21,items:[0,1,2].map(i=>({item:{...task,id:'task_'+String(i).repeat(32),approved_date:i===0?null:'2030-01-01'},reason:'joint-task'}))};assert.throws(()=>home.parse(canonical(dates),'i2-clara'));checks++;
assert.throws(()=>home.parse(canonical(value).replace('"synthetic_only":true','"synthetic_only":true,"synthetic_only":true'),'i2-clara'));checks++;
assert.deepEqual(Object.keys(home.copy['zh-CN']).sort(),Object.keys(home.copy['en-US']).sort());checks++;
console.log(checks+' I9 strict DTO / classification / ordering checks passed.');
