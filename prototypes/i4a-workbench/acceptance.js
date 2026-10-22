(function(root){
  'use strict';
  const zh={notice:'本地后端连接测试 · 虚构数据 · 人工确认后保存',readonly:'仅待确认接受已连接。编辑、归档和外部操作尚未开放。',
    total:'当前可查看',empty:'当前没有可查看的待确认事项。',question:'需要更多信息',details:'查看详情',accept:'加入家庭待办',blocked:'暂不能接受；仍需核实信息。',
    preview:'确认加入家庭待办',effect:'确认后将创建一项家庭待办，并移出待确认。仅保存在本次本地测试中；不执行预约、付款或其他外部活动。',
    confirm:'确认接受',cancel:'取消',close:'关闭',loading:'正在核对确认预览。',failed:'无法准备预览。未发出接受请求；如先前提交中断，请先核对最近一次接受。',
    submitting:'已提交，正在核对结果。关闭窗口不会撤回请求。',unknown:'接受结果尚未确认。不要重复提交；请核对最近一次接受。',
    recover:'核对最近一次接受',committed:'已确认接受成功，正在从后端重新读取家庭待办。',notApplied:'已核实本次请求未生效。请重新读取；如仍需接受，请重新预览并确认。',
    stale:'信息或权限版本已变化。本次未接受，请重新读取并确认。',unavailable:'本次未接受，当前权限或信息不支持此操作。',conflict:'请求内容冲突。本次未接受，请重新核对。',
    none:'当前测试会话没有接受提交记录。',joint:'共同负责',clara:'Clara',devon:'Devon',date:'日期',noDate:'未设置日期',school:'安排学校活动',visit:'安排家庭到访'};
  const en={notice:'Local backend test · Fictional data · Explicit acceptance',readonly:'Only Pending acceptance is connected. Editing, archive and external operations are unavailable.',
    total:'Currently available',empty:'No Pending items are currently available to you.',question:'More information needed',details:'Details',accept:'Add household task',blocked:'Not eligible for acceptance; more verification is needed.',
    preview:'Confirm household task',effect:'Confirmation creates one household task and removes the proposal from Pending. Saved only for this local test run; no booking, payment or other external activity is performed.',
    confirm:'Confirm acceptance',cancel:'Cancel',close:'Close',loading:'Checking the confirmation preview.',failed:'Preview unavailable. No acceptance was submitted. If a prior submission was interrupted, check the latest acceptance first.',
    submitting:'Submitted; checking the outcome. Closing this window does not withdraw the request.',unknown:'Acceptance outcome is unknown. Do not resubmit; check the latest acceptance.',
    recover:'Check latest acceptance',committed:'Acceptance is verified. Reloading household tasks from the backend.',notApplied:'Verified not applied. Reload; if still wanted, prepare and explicitly confirm a new preview.',
    stale:'Information or permission revisions changed. Not accepted; reload before confirming again.',unavailable:'Not accepted. Current rights or information do not support this operation.',conflict:'Changed-intent conflict. Not accepted; check again.',
    none:'This test session has no acceptance submission.',joint:'Jointly managed',clara:'Clara',devon:'Devon',date:'Date',noDate:'No date set',school:'Arrange school session',visit:'Arrange home visit'};
  if(Object.keys(zh).sort().join()!==Object.keys(en).sort().join())throw Error('Translation contract');
  const outcomes=['COMMITTED','COMMITTED-replay','NOT_APPLIED-stale','NOT_APPLIED-changed-intent','NOT_APPLIED-canceled','NOT_APPLIED-unavailable','NOT_APPLIED-verified-absence','UNKNOWN-reconciliation-required'];
  const keys=(v,k)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).sort().join()===k.split(',').sort().join();
  const integer=(v,min,max)=>Number.isSafeInteger(v)&&v>=min&&v<=max;
  const id=v=>typeof v==='string'&&/^[a-z][a-z0-9_-]{0,63}$/.test(v);
  const handle=v=>typeof v==='string'&&/^[0-9a-f]{32}$/.test(v);
  const date=v=>v===null||(typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v);
  const step=v=>['school-session','home-visit'].includes(v);
  function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
  function decode(raw){if(typeof raw!=='string'||raw.length>16384||/[^\x20-\x7e]/.test(raw))throw Error('contract');const value=JSON.parse(raw);if(canonical(value)!==raw)throw Error('contract');return value;}
  function parse(raw,limit,offset){
    const v=decode(raw);
    if(!keys(v,'schema,synthetic_only,pagination,pending')||v.schema!=='i4a-pending-page-v1'||v.synthetic_only!==true||
      !keys(v.pagination,'limit,offset')||v.pagination.limit!==limit||v.pagination.offset!==offset||!integer(limit,1,20)||!integer(offset,0,1000000)||
      !keys(v.pending,'items,total,has_more'))throw Error('contract');
    const p=v.pending;
    if(!Array.isArray(p.items)||!integer(p.total,0,1000000)||p.items.length!==Math.min(limit,Math.max(0,p.total-offset))||typeof p.has_more!=='boolean'||p.has_more!==(offset+p.items.length<p.total))throw Error('contract');
    let previous='';
    for(const r of p.items){if(!keys(r,'id,revision,step,supported_date,can_accept')||!id(r.id)||r.id<=previous||!integer(r.revision,1,1000000)||
      !(r.step===null||step(r.step))||!date(r.supported_date)||typeof r.can_accept!=='boolean'||(r.can_accept&&!step(r.step)))throw Error('contract');previous=r.id;}
    return v;
  }
  function preview(raw,requested){const v=decode(raw);if(!keys(v,'schema,synthetic_only,receipt,id,revision,step,assignee,approved_date')||v.schema!=='i4a-acceptance-preview-v1'||v.synthetic_only!==true||!handle(v.receipt)||v.id!==requested||!integer(v.revision,1,1000000)||!step(v.step)||!['joint','i2-clara','i2-devon'].includes(v.assignee)||!date(v.approved_date))throw Error('contract');return v;}
  function result(raw){const v=decode(raw);if(!keys(v,'schema,synthetic_only,outcome,receipt')||v.schema!=='i4a-acceptance-result-v1'||v.synthetic_only!==true||!outcomes.includes(v.outcome)||!(v.receipt===null||handle(v.receipt))||(v.receipt===null&&!['NOT_APPLIED-verified-absence','UNKNOWN-reconciliation-required'].includes(v.outcome)))throw Error('contract');return v;}
  function create({main,dialog,body,api,locale,close,committed,refresh,page}){
    let currentPreview=null,inspected=null,attempt=null,epoch=0,sessionEpoch=0,lastMember=null,preparing=false,recovering=false;
    const tr=k=>{const v=(locale()==='zh-CN'?zh:en)[k];if(typeof v!=='string')throw Error('Translation contract');return v;};
    const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
    const button=(text,fn)=>{const n=el('button',text);n.type='button';n.addEventListener('click',fn);return n;};
    const dismiss=()=>{epoch++;currentPreview=null;inspected=null;preparing=false;};
    function status(){
      main.querySelector('.acceptance-status')?.remove();
      if(main.dataset.view!=='pending')return;
      const box=el('section',undefined,'acceptance-status');box.setAttribute('role','status');box.setAttribute('aria-live','polite');
      if(attempt)box.append(el('p',tr(attempt.message)));
      const check=button(tr('recover'),recover);check.disabled=recovering||attempt?.outcome==='submitting';box.append(check);main.append(box);
    }
    function modal(title){body.replaceChildren();const top=el('div',undefined,'dialog-top');top.append(el('small',tr('notice')),button(tr('close'),()=>{close();main.focus();}));const h=el('h2',title);h.id='dialog-title';body.append(top,h);if(!dialog.open)dialog.showModal();}
    function render(p){
      main.append(el('p',tr('total')+'：'+p.total));
      if(!p.items.length)main.append(el('p',tr('empty'),'empty'));
      else{const rows=el('div',undefined,'cards wide');for(const r of p.items){const card=el('article',undefined,'card');card.dataset.pending=r.id;
        card.append(el('h3',tr(r.step==='school-session'?'school':r.step==='home-visit'?'visit':'question')));
        card.append(el('p',r.supported_date===null?tr('noDate'):tr('date')+'：'+r.supported_date));
        if(!r.can_accept)card.append(el('p',tr('blocked')));
        card.append(button(tr(r.can_accept?'accept':'details'),()=>open(r)));rows.append(card);}main.append(rows);}
      status();
    }
    async function open(row){
      if(attempt&&(attempt.outcome==='submitting'||attempt.message==='unknown')){status();return;}
      close();inspected={id:row.id,revision:row.revision};const request=epoch,identity=sessionEpoch;preparing=true;modal(tr(row.can_accept?'preview':'question'));
      if(!row.can_accept){body.append(el('p',tr('blocked')));preparing=false;return;}
      body.append(el('p',tr('loading')));
      try{
        const p=preview(await api('/api/pending/preview',true,{id:row.id}),row.id);
        if(request!==epoch||identity!==sessionEpoch)return;preparing=false;currentPreview=p;inspected={id:p.id,revision:p.revision};modal(tr('preview'));
        body.append(el('h3',tr(p.step==='school-session'?'school':'visit')),el('p',tr(p.assignee==='joint'?'joint':p.assignee==='i2-clara'?'clara':'devon')),
          el('p',p.approved_date===null?tr('noDate'):tr('date')+'：'+p.approved_date),el('p',tr('effect')));
        const actions=el('div',undefined,'connection-actions');const confirm=button(tr('confirm'),()=>submit(p,confirm));confirm.className='primary';
        actions.append(confirm,button(tr('cancel'),()=>{close();main.focus();}));body.append(actions);
      }catch(_){if(request!==epoch||identity!==sessionEpoch)return;preparing=false;modal(tr('preview'));body.append(el('p',tr('failed')));}
    }
    async function submit(p,control){
      if(currentPreview!==p||attempt?.outcome==='submitting'||attempt?.message==='unknown')return;
      const identity=sessionEpoch;control.disabled=true;attempt={receipt:p.receipt,outcome:'submitting',message:'submitting'};currentPreview=null;
      modal(tr('preview'));body.append(el('p',tr('submitting')));
      let value;
      try{value=result(await api('/api/pending/accept',true,{receipt:p.receipt,confirm:true}));if(value.receipt!==p.receipt)throw Error('contract');}
      catch(_){value={outcome:'UNKNOWN-reconciliation-required',receipt:p.receipt};}
      if(identity===sessionEpoch)finish(value);
    }
    function finish(value){
      const accepted=['COMMITTED','COMMITTED-replay'].includes(value.outcome);
      const message=accepted?'committed':value.outcome==='UNKNOWN-reconciliation-required'?'unknown':value.outcome==='NOT_APPLIED-stale'?'stale':value.outcome==='NOT_APPLIED-unavailable'?'unavailable':value.outcome==='NOT_APPLIED-changed-intent'?'conflict':value.receipt===null?'none':'notApplied';
      attempt={...value,message};close();
      if(accepted){attempt=null;committed();}else refresh(); // Reads only; never repeat an acceptance.
    }
    async function recover(){
      if(recovering||attempt?.outcome==='submitting')return;const identity=sessionEpoch;recovering=true;status();
      let value;
      try{const receipt=attempt?.receipt;value=result(await api(receipt?'/api/pending/outcome':'/api/pending/recover',true,receipt?{receipt}:{}));}
      catch(_){value={outcome:'UNKNOWN-reconciliation-required',receipt:attempt?.receipt||null};}
      if(identity!==sessionEpoch)return;recovering=false;finish(value);
    }
    function revalidate(p){
      if(inspected){const row=p?.items.find(r=>r.id===inspected.id);if(!row||row.revision!==inspected.revision||(currentPreview&&!row.can_accept))close();}
      // A late preview must not reopen or authorize a record removed by a newer read.
      if(preparing&&!p)close();
    }
    function resetSession(){sessionEpoch++;dismiss();attempt=null;recovering=false;lastMember=null;}
    function bindMember(member){if(lastMember!==member){resetSession();lastMember=member;}}
    return {render,parse,dismiss,revalidate,resetSession,bindMember,copy:k=>Object.hasOwn(zh,k)?tr(k):null};
  }
  root.SamasAcceptance=Object.freeze({create,parse,preview,result});
  if(typeof module!=='undefined')module.exports=root.SamasAcceptance;
})(globalThis);
