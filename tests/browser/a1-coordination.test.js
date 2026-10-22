'use strict';
// Deterministic unit faults around the ACTUAL refresh function. No browser/server claim.
const {test} = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
globalThis.SamasTaskContract = require('../../prototypes/i3-workbench/contract.js');
globalThis.SamasAcceptance = require('../../prototypes/i4a-workbench/acceptance.js');
const editing = require('../../prototypes/i4b-workbench/editing.js');
const canonical = v => Array.isArray(v) ? '[' + v.map(canonical).join(',') + ']' : v && typeof v === 'object' ? '{' + Object.keys(v).sort().map(k => JSON.stringify(k) + ':' + canonical(v[k])).join(',') + '}' : JSON.stringify(v);
const task = {id:'task_'+'a'.repeat(32),step:'school-session',assignee:'joint',status:'completed',approved_date:null,revision:1,can_edit:true};
const pending = {id:'a1-fictional-question',revision:1,step:null,supported_date:null,can_accept:false};
const tasks = () => ({schema:'i4b-task-page-v1',synthetic_only:true,pagination:{limit:12,offset:0},tasks:{items:[{...task}],total:1,has_more:false}});
const proposals = () => ({schema:'i4a-pending-page-v1',synthetic_only:true,pagination:{limit:12,offset:0},pending:{items:[{...pending}],total:1,has_more:false}});
const gate = () => { let release; const promise = new Promise(r => release=r); return {promise,release}; };
function harness({stage='i4b', handler, crlf=false}={}) {
  const calls=[], renders=[], epochs=[], validations=[];
  const node=()=>({dataset:{},textContent:'',open:false,append(){},insertBefore(){},replaceChildren(){},addEventListener(){},close(){this.open=false;},focus(){}});
  const nodes=new Map(), get=id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);};
  const document={documentElement:{dataset:{connection:stage}},getElementById:get,querySelector:()=>node()};
  const adapter={taskParse:stage==='i4b'?editing.taskParse:undefined,parse:SamasAcceptance.parse,dismiss(){},resetSession(){epochs.push('reset');},bindMember(m){epochs.push(m);},copy:()=>null,
    revalidate:p=>validations.push(['pending',p]),revalidateTasks:p=>validations.push(['tasks',p]),status(){}};
  const c={document,matchMedia:()=>({matches:false,addEventListener(){}}),addEventListener(){},setTimeout:()=>0,clearTimeout(){},
    AbortSignal,TextDecoder,Uint8Array,SamasTaskContract,
    SamasEditing:{create:()=>adapter},SamasAcceptance:{create:()=>adapter},
    async fetch(url,options){calls.push(url);let value=handler?await handler(url,options,calls):undefined;
      if(value===undefined)value=url==='/api/session'?{state:'active',member:'i2-clara'}:url.startsWith('/api/tasks?')?tasks():proposals();
      if(url.includes('responsibility=')&&value.schema==='i4b-task-page-v1'){const q=new URL(url,'http://fiction.invalid').searchParams;value={...value,schema:'i4b-task-page-v2',query:{responsibility:q.get('responsibility'),step:q.get('step')}};}
      const raw=typeof value==='string'?value:canonical(value),bytes=new TextEncoder().encode(raw);let read=false;
      return {ok:true,headers:{get:()=> 'application/json'},body:{getReader:()=>({read:async()=>read?{done:true}:(read=true,{done:false,value:bytes}),cancel:async()=>{}})}};
    }};
  let source=fs.readFileSync(path.join(root,'prototypes/i3-workbench/workbench.js'),'utf8');
  if(crlf)source=source.replace(/\r?\n/g,'\r\n');
  source=source.replace(/\r\n/g,'\n');
  const tail='  refresh();\n})();'; assert(source.endsWith(tail+'\n'));
  source=source.slice(0,-(tail.length+1))+`  render=()=>{globalThis.capture({state,member,current,view});};
  globalThis.unit={refresh,navigate,snapshot:()=>({state,member,current,view})};\n})();\n`;
  c.capture=v=>renders.push(JSON.parse(JSON.stringify(v)));vm.runInNewContext(source,c);
  return {...c.unit,calls,renders,epochs,validations,snapshot:()=>JSON.parse(JSON.stringify(c.unit.snapshot()))};
}
test('pair is published only after strict Tasks, Pending and final current member',async()=>{
  const h=harness();await h.refresh();assert.equal(h.snapshot().state,'active');assert.equal(h.snapshot().current.tasks.total,1);
  assert.equal(h.snapshot().current.pending.items[0].can_accept,false);
  assert.deepEqual(h.calls,['/api/session','/api/tasks?limit=12&offset=0','/api/pending?limit=12&offset=0','/api/session']);
  assert.equal(h.renders.filter(r=>r.state==='active').length,1);
  assert.deepEqual(h.validations.map(v=>v[0]),['pending','tasks']);
});
for(const collection of ['tasks','pending'])for(const fault of ['connection','malformed','schema'])test(collection+' '+fault+' clears entire previously authorized pair',async()=>{
  let fail=false;const h=harness({handler:url=>{if(fail&&url.startsWith('/api/'+collection+'?')){if(fault==='connection')throw Error('private failure must not surface');return fault==='schema'?{schema:'wrong'}:'{';}}});
  await h.refresh();assert(h.snapshot().current);fail=true;await h.refresh(true);
  assert.equal(h.snapshot().current,null);assert.equal(h.snapshot().member,null);assert.equal(h.snapshot().state,fault==='connection'?'connection':'contract');
});
test('unreleased Pending never publishes successful Tasks as a partial Home',async()=>{
  const g=gate();let reached=false;const h=harness({handler:async url=>{if(url.startsWith('/api/pending?')){reached=true;await g.promise;}}});
  const flight=h.refresh();while(!reached)await new Promise(r=>setImmediate(r));assert.equal(h.snapshot().current,null);g.release();await flight;assert.equal(h.snapshot().state,'active');
});
test('final member mismatch withholds both collections and resets session-bound intent',async()=>{
  let sessions=0;const h=harness({handler:url=>url==='/api/session'?{state:'active',member:++sessions===1?'i2-clara':'i2-devon'}:undefined});
  await h.refresh();assert.equal(h.snapshot().state,'access');assert.equal(h.snapshot().current,null);assert(h.epochs.includes('reset'));
});
test('unchanged background authorization keeps controls mounted but performs all reads',async()=>{
  const h=harness();await h.refresh();const renders=h.renders.length;await h.refresh(true);
  assert.equal(h.renders.length,renders);assert.equal(h.calls.length,8);assert.equal(h.snapshot().state,'active');
});
test('changed Pending assertion is published and revalidated, not stale cached eligibility',async()=>{
  let revision=1;const h=harness({handler:url=>url.startsWith('/api/pending?')?{...proposals(),pending:{...proposals().pending,items:[{...pending,revision}]}}:undefined});
  await h.refresh();revision=2;await h.refresh(true);assert.equal(h.snapshot().current.pending.items[0].revision,2);
  assert.equal(h.validations.filter(v=>v[0]==='pending').at(-1)[1].items[0].revision,2);
});
test('late old Home response cannot overwrite newly authorized Tasks page',async()=>{
  const g=gate();let reached=false,held=true;const h=harness({handler:async url=>{if(held&&url.startsWith('/api/pending?')){reached=true;await g.promise;}}});
  const flight=h.refresh();while(!reached)await new Promise(r=>setImmediate(r));held=false;await h.navigate('tasks');g.release();await flight;
  assert.equal(h.snapshot().view,'tasks');assert.equal(h.snapshot().state,'active');assert.equal(h.snapshot().current.pending,undefined);
});
test('background member change removes old pair before new collection is released',async()=>{
  const g=gate();let switched=false,reached=false;const h=harness({handler:async url=>{
    if(url==='/api/session')return {state:'active',member:switched?'i2-devon':'i2-clara'};
    if(switched&&url.startsWith('/api/tasks?')){reached=true;await g.promise;}
  }});await h.refresh();switched=true;const flight=h.refresh(true);while(!reached)await new Promise(r=>setImmediate(r));
  assert.equal(h.snapshot().current,null);assert.equal(h.snapshot().member,null);g.release();await flight;assert.equal(h.snapshot().member,'i2-devon');
});
for(const stage of ['i3','i4a'])test(stage+' Home preserves original single collection boundary',async()=>{
  const h=harness({stage,handler:url=>{if(url.startsWith('/api/tasks?')){const p=tasks();p.schema='i3-fictional-task-page-v1';p.tasks.items=p.tasks.items.map(({can_edit,...row})=>row);return p;}}});
  await h.refresh();assert.equal(h.snapshot().state,'active');assert.deepEqual(h.calls,['/api/session','/api/tasks?limit=12&offset=0']);
});

test('Windows CRLF source executes the same actual refresh contract',async()=>{
  const h=harness({crlf:true});await h.refresh();assert.equal(h.snapshot().state,'active');assert.equal(h.snapshot().current.pending.total,1);
});
