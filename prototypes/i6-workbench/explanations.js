(function(root){
  'use strict';
  const copy={
    'zh-CN':{title:'了解这项建议',what:'发生了什么',why:'判断依据',next:'下一步',source:'来源：受控虚构测试输入',
      school:'这是一条学校活动相关测试事项。',visit:'这是一条家庭到访相关测试事项。',question:'这是一条尚需核实的测试事项。',
      supported:'测试输入将行动证据标记为支持；不证明现实义务。',conflicting:'测试输入中的行动依据存在冲突。',unsupported:'测试输入未支持确定行动。',none:'测试输入没有明确的行动依据。',unavailable:'本代输入未形成可用的业务解释。',
      'structured-support':'当前结构化标记支持所展示的建议步骤。','conflicting-action-evidence':'依据冲突，不能据此确定需要执行的行动。',
      'missing-action-step':'当前待确认尚无可接受的具体步骤。','insufficient-action-evidence':'缺少足够的行动依据，需要更多信息。',
      'independent-service-only':'重要服务部分仍需核实；促销和优惠有效期不构成家庭义务。','current-evidence-unavailable':'信息或授权已有变化，需要重新核实。恢复访问不会恢复旧的接受能力。',
      unknownFacts:'测试输入没有提供通知正文或其他现实事实，请勿自行补全。',clear:'当前测试评估未标记风险，不代表现实安全。','high-risk':'当前测试评估标记风险，不能接受。',unknown:'评估尚不确定或已失效，不能据此接受。',neutral:'当前无法确认是否可接受。',
      candidate:'可查看接受预览，再单独确认。仅查看或关闭不会创建待办。',blocked:'仍需核实，当前不提供接受操作。',preview:'查看接受预览',close:'关闭',loading:'正在读取当前说明。',failed:'当前无法读取说明，请重新读取待确认列表。',date:'已有日期',noDate:'未提供日期',boundary:'虚构测试依据 · 不执行外部活动'},
    'en-US':{title:'Understand this suggestion',what:'What happened',why:'Basis for the suggestion',next:'Next step',source:'Source: controlled fictional test input',
      school:'A school-activity test item.',visit:'A home-visit test item.',question:'A test item requiring further verification.',
      supported:'The test input marks action evidence as supported; it does not prove a real-world obligation.',conflicting:'The test input contains conflicting action evidence.',unsupported:'The test input does not support a definite action.',none:'The test input provides no definite action evidence.',unavailable:'This generation did not produce a usable business explanation.',
      'structured-support':'The current structured marker supports the displayed proposed step.','conflicting-action-evidence':'The evidence conflicts and cannot establish a definite action.',
      'missing-action-step':'This Pending item has no acceptable concrete step yet.','insufficient-action-evidence':'Action evidence is insufficient; more information is needed.',
      'independent-service-only':'The important service part needs verification; promotions and offer expiry do not establish household obligations.','current-evidence-unavailable':'Information or authorization changed; verify again. Restored access does not revive old acceptance eligibility.',
      unknownFacts:'The test input supplies no notification body or other real-world facts. Do not invent missing details.',clear:'The current test assessment marks no risk; this is not proof of real-world safety.','high-risk':'The current test assessment marks risk; acceptance is unavailable.',unknown:'The assessment is uncertain or no longer current; do not accept on this basis.',neutral:'Acceptance eligibility cannot currently be established.',
      candidate:'Inspect the acceptance preview, then confirm separately. Reading or closing creates no task.',blocked:'More verification is needed; acceptance is unavailable.',preview:'Review acceptance preview',close:'Close',loading:'Loading the current explanation.',failed:'Explanation unavailable. Reload the Pending list.',date:'Existing date',noDate:'No date provided',boundary:'Fictional test evidence · No external activity'}
  };
  if(Object.keys(copy['zh-CN']).sort().join()!==Object.keys(copy['en-US']).sort().join())throw Error('Translation contract');
  const keys=(v,list)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).sort().join()===list.split(',').sort().join();
  function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
  function parse(raw,row){
    if(typeof raw!=='string'||raw.length>4096||/[^\x20-\x7e]/.test(raw))throw Error('contract');const v=JSON.parse(raw);
    if(!row||typeof row.id!=='string'||!/^[a-z][a-z0-9_-]{0,63}$/.test(row.id)||!Number.isSafeInteger(row.revision)||row.revision<1||row.revision>1000000||![null,'school-session','home-visit'].includes(row.step)||typeof row.can_accept!=='boolean'||!(row.supported_date===null||(typeof row.supported_date==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(row.supported_date)&&Number.isFinite(Date.parse(row.supported_date))&&new Date(row.supported_date).toISOString().slice(0,10)===row.supported_date)))throw Error('contract');
    const reasons=['structured-support','conflicting-action-evidence','missing-action-step','insufficient-action-evidence','independent-service-only','current-evidence-unavailable'];
    if(canonical(v)!==raw||!keys(v,'schema,synthetic_only,id,revision,generation,definition,source_kind,step,supported_date,action,reasons,safety,can_accept')||
      v.schema!=='i6-pending-explanation-v1'||v.synthetic_only!==true||v.id!==row.id||v.revision!==row.revision||
      !Number.isSafeInteger(v.generation)||v.generation<1||v.generation>1000||v.definition!=='i5-fictional-routing-v1-stagea-v2'||v.source_kind!=='structured-fictional-input'||
      v.step!==row.step||v.supported_date!==row.supported_date||v.can_accept!==row.can_accept||typeof v.can_accept!=='boolean'||
      !['supported','conflicting','unsupported','none','unavailable'].includes(v.action)||!Array.isArray(v.reasons)||v.reasons.length!==1||!reasons.includes(v.reasons[0])||
      ![null,'clear','high-risk','unknown'].includes(v.safety)||
      (v.can_accept&&(v.safety!=='clear'||v.action!=='supported'||!['school-session','home-visit'].includes(v.step)||v.reasons[0]!=='structured-support'))||
      (v.action==='unavailable'&&(v.can_accept||v.reasons[0]!=='current-evidence-unavailable'))||
      (v.action==='conflicting'&&(v.can_accept||v.reasons[0]!=='conflicting-action-evidence')))throw Error('contract');
    const reason=v.reasons[0];
    if((reason==='structured-support'&&(v.action!=='supported'||v.step===null))||(reason==='missing-action-step'&&(v.action!=='supported'||v.step!==null))||
      (reason==='conflicting-action-evidence'&&v.action!=='conflicting')||(reason==='current-evidence-unavailable'&&v.action!=='unavailable')||
      (['insufficient-action-evidence','independent-service-only'].includes(reason)&&!['none','unsupported'].includes(v.action)))throw Error('contract');
    return v;
  }
  function create({main,dialog,body,api,locale,close,personal},preview,personalActions=null,personalOpen=null){
    let inspected=null,value=null,epoch=0,request=0,session=0,member=null;
    const tr=k=>{const s=copy[locale()]?.[k];if(typeof s!=='string')throw Error('Translation contract');return s;};
    const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
    const button=(text,fn)=>{const n=el('button',text);n.type='button';n.addEventListener('click',fn);return n;};
    function dismiss(){epoch++;request++;inspected=null;value=null;delete body.dataset.explanation;}
    function modal(){if(personal?.explanationModal)return personal.explanationModal(inspected);body.replaceChildren();const top=el('div');top.className='dialog-top';const exit=button(tr('close'),()=>{close();main.focus();});top.append(el('small',tr('boundary')),exit);const h=el('h2',tr('title'));h.id='dialog-title';body.append(top,h);if(!dialog.open)dialog.showModal();exit.focus();return body;}
    function display(v){
      if(personal?.details){const row=inspected;personal.details(v,row,
        ()=>{if(inspected===row&&value===v)preview(row);},
        ()=>{if(inspected===row&&value===v)personalOpen(row,()=>open(row));});body.dataset.explanation=v.id;return;}
      modal();body.dataset.explanation=v.id;const what=el('section');what.append(el('h3',tr('what')),el('p',tr('source')),el('p',tr(v.step==='school-session'?'school':v.step==='home-visit'?'visit':'question')),el('p',tr(v.action)),el('p',v.supported_date===null?tr('noDate'):tr('date')+': '+v.supported_date));
      const why=el('section');why.append(el('h3',tr('why')));for(const reason of v.reasons)why.append(el('p',tr(reason)));why.append(el('p',tr(v.safety===null?'neutral':v.safety)),el('p',tr('unknownFacts')));
      const next=el('section');next.append(el('h3',tr('next')),el('p',tr(v.can_accept?'candidate':'blocked')));
      if(v.can_accept){const control=button(tr('preview'),()=>{const row=inspected;if(row&&value===v)preview(row);});control.className='primary';next.append(control);}body.append(what,why,next);if(personalActions)body.append(personalActions(inspected));
    }
    async function load(row,initial){
      const n=++request,e=epoch,s=session;
      try{
        const v=parse(await api('/api/pending/explanation?id='+row.id+'&revision='+row.revision,false),row);
        if(n!==request||e!==epoch||s!==session||inspected?.id!==row.id)return;
        if(initial){value=v;display(v);}else if(canonical(value)!==canonical(v)){close();main.focus();}
      }catch(_){if(n!==request||e!==epoch||s!==session)return;if(!initial){close();main.focus();}else{dismiss();modal().append(el('p',tr('failed')));}}
    }
    function open(row){close();delete body.dataset.explanation;inspected={...row};modal().append(el('p',tr('loading')));load(row,true);}
    function revalidate(page){if(!inspected)return;const row=page?.items.find(r=>r.id===inspected.id);if(!row||canonical(row)!==canonical(inspected)){close();main.focus();return;}load(row,value===null);}
    function resetSession(){session++;dismiss();member=null;delete body.dataset.explanation;}
    function bindMember(v){if(member!==v){resetSession();member=v;}}
    return {open,dismiss,revalidate,resetSession,bindMember};
  }
  const editing=root.SamasEditing;
  if(editing){root.SamasEditing=Object.freeze({...editing,create(options){
    let detail;const inspectPending=(row,handling=false)=>handling?base.personalDetail(row,()=>inspectPending(row)):row.id.startsWith('i5_')?detail.open(row):options.personal?base.personalDetail(row):base.openPending(row);
    const base=editing.create({...options,pendingPreview:row=>options.api('/api/pending/preview',true,{id:row.id,revision:row.revision}),pendingDetails:inspectPending});detail=create(options,row=>base.openPending(row),base.reviewActions,(row,back)=>base.personalDetail(row,back));
    return {...base,inspectPending,dismiss(){base.dismiss();detail.dismiss();},revalidate(p){base.revalidate(p);detail.revalidate(p);},
      resetSession(){base.resetSession();detail.resetSession();},bindMember(v){base.bindMember(v);detail.bindMember(v);}};
  }});}
  root.SamasExplanations=Object.freeze({parse,copy});
  if(typeof module!=='undefined')module.exports=root.SamasExplanations;
})(globalThis);
