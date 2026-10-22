(function(root){
  'use strict';
  const keys=(v,list)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).sort().join()===list.split(',').sort().join();
  const integer=(v,min,max)=>Number.isSafeInteger(v)&&v>=min&&v<=max;
  function canonical(v){
    if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';
    if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';
    return JSON.stringify(v);
  }
  function parse(raw,limit,offset){
    if(typeof raw!=='string'||raw.length>16384||/[^\x20-\x7e]/.test(raw))throw Error('contract');
    const v=JSON.parse(raw);
    // Server emits canonical ASCII JSON. This also rejects duplicate keys/noncanonical numbers.
    if(canonical(v)!==raw||!keys(v,'schema,synthetic_only,pagination,tasks')||v.schema!=='i3-fictional-task-page-v1'||v.synthetic_only!==true||
      !keys(v.pagination,'limit,offset')||v.pagination.limit!==limit||v.pagination.offset!==offset||
      !integer(limit,1,20)||!integer(offset,0,1000000)||!keys(v.tasks,'items,total,has_more'))throw Error('contract');
    const p=v.tasks;
    if(!Array.isArray(p.items)||!integer(p.total,0,1000000)||p.items.length!==Math.min(limit,Math.max(0,p.total-offset))||
       typeof p.has_more!=='boolean'||p.has_more!==(offset+p.items.length<p.total))throw Error('contract');
    let previous='';
    for(const r of p.items){
      if(!keys(r,'id,step,assignee,status,approved_date,revision')||typeof r.id!=='string'||!/^task_[0-9a-f]{32}$/.test(r.id)||r.id<=previous||
        !['school-session','home-visit'].includes(r.step)||!['joint','i2-clara','i2-devon'].includes(r.assignee)||
        !['pending','completed'].includes(r.status)||!integer(r.revision,1,1000000))throw Error('contract');
      if(r.approved_date!==null){
        if(typeof r.approved_date!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(r.approved_date)||
          !Number.isFinite(Date.parse(r.approved_date))||new Date(r.approved_date).toISOString().slice(0,10)!==r.approved_date)throw Error('contract');
      }
      previous=r.id;
    }
    return v;
  }
  root.SamasTaskContract=Object.freeze({parse});
  if(typeof module!=='undefined')module.exports=root.SamasTaskContract;
})(globalThis);
