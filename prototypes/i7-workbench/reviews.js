(function(root){
 'use strict';
 const operations=Object.freeze(['review','defer','needs-information']);
 const states=['all','unhandled','viewed','deferred','needs-information'];
 const copy={
  'zh-CN':{recordHandling:'记录处理方式',back:'返回',chooseHelp:'选择处理方式后，再确认保存。',preparing:'正在核对当前处理预览。',ready:'预览已核对。确认保存才会记录你的选择。',previewFailed:'当前无法准备处理记录。未提交，请重新读取后再试。',schoolTitle:'安排学校活动',visitTitle:'安排家庭到访',questionTitle:'待核实事项',detailTitle:'事项详情',detailBody:'事项内容',legacyBoundary:'仅显示当前获准的测试事项；本事项没有 I5 结构化解释。',readonly:'支持个人处理、接受与任务编辑；不执行外部活动。',handling:'处理这项待确认',personalBoundary:'仅记录你的处理方式，不创建待办、不联系来源，也不改变安全评估。',review:'标记已查看',defer:'稍后处理','needs-information':'需要更多信息',
   reviewEffect:'保存你已查看当前信息的记录；仍未接受行动建议。',deferEffect:'记录稍后处理；事项仍未解决，不会自动提醒。','needs-informationEffect':'记录你还需要更多信息；不会发送询问。',savePersonal:'确认保存',
   all:'全部',unhandled:'尚未处理',viewed:'我已查看',deferred:'我已暂缓',needs:'我在等待更多信息',filter:'我的处理状态',
   reviewSaved:'已记录你已查看',deferSaved:'已记录稍后处理',needsSaved:'已记录需要更多信息',empty:'当前分类没有可查看的待确认事项。'},
  'en-US':{recordHandling:'Record my handling',back:'Back',chooseHelp:'Select a handling option, then explicitly confirm to save.',preparing:'Checking the current handling preview.',ready:'Preview checked. Confirm save to record your choice.',previewFailed:'Handling preview unavailable. Nothing submitted; reload before trying again.',schoolTitle:'Arrange school session',visitTitle:'Arrange home visit',questionTitle:'Item to verify',detailTitle:'Item details',detailBody:'Item content',legacyBoundary:'Only the currently authorized test item is shown; no I5 structured explanation exists for this item.',readonly:'Personal handling, acceptance and task editing only; no external execution.',handling:'Handle this Pending item',personalBoundary:'Your handling only. No task, contact or safety clearance.',review:'Mark viewed',defer:'Handle later','needs-information':'Need more information',
   reviewEffect:'Record that you viewed the current information; this does not accept the suggestion.',deferEffect:'Record handling later. It remains unresolved; no automatic reminder.','needs-informationEffect':'Record that you need more information. No inquiry is sent.',savePersonal:'Confirm save',
   all:'All',unhandled:'Not handled',viewed:'Viewed by me',deferred:'Deferred by me',needs:'Awaiting more information',filter:'My handling status',
   reviewSaved:'Your viewed record saved',deferSaved:'Handle-later record saved',needsSaved:'Need-more-information record saved',empty:'No authorized Pending items in this category.'}
 };
 if(Object.keys(copy['zh-CN']).sort().join()!==Object.keys(copy['en-US']).sort().join())throw Error('Translation contract');
 const keys=(v,k)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).sort().join()===k.split(',').sort().join();
 function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
 function decode(raw){if(typeof raw!=='string'||raw.length>16384||/[^\x20-\x7e]/.test(raw))throw Error('contract');const v=JSON.parse(raw);if(canonical(v)!==raw)throw Error('contract');return v;}
 function parse(raw,limit,offset,state='all'){
  const v=decode(raw);if(!keys(v,'schema,synthetic_only,pagination,pending,query')||v.schema!=='i7-personal-pending-page-v1'||!keys(v.query,'state,step')||v.query.state!==state||!states.includes(state)||v.query.step!==null||!Array.isArray(v.pending?.items))throw Error('contract');
  for(const r of v.pending.items){if(!keys(r,'id,revision,step,supported_date,can_accept,can_review,reviewed,disposition')||typeof r.can_review!=='boolean'||typeof r.reviewed!=='boolean'||!['active','deferred','needs-information'].includes(r.disposition))throw Error('contract');
   if((state==='viewed'&&(!r.reviewed||r.disposition!=='active'))||(state==='unhandled'&&(r.reviewed||r.disposition!=='active'))||(state==='deferred'&&r.disposition!=='deferred')||(state==='needs-information'&&r.disposition!=='needs-information'))throw Error('contract');}
  const base={schema:'i4a-pending-page-v1',synthetic_only:v.synthetic_only,pagination:v.pagination,pending:{...v.pending,items:v.pending.items.map(({can_review,reviewed,disposition,...r})=>r)}};
  root.SamasAcceptance.parse(canonical(base),limit,offset);return v;
 }
 function preview(raw,row,operation){const v=decode(raw);if(!keys(v,'schema,synthetic_only,id,revision,operation,receipt')||v.schema!=='i7-personal-preview-v1'||v.synthetic_only!==true||v.id!==row.id||v.revision!==row.revision||!operations.includes(operation)||v.operation!==operation||typeof v.receipt!=='string'||! /^[0-9a-f]{32}$/.test(v.receipt))throw Error('contract');return v;}
 function result(raw){const v=decode(raw);if(v.schema!=='i7-write-result-v1'||![null,'accept','edit',...operations].includes(v.operation))throw Error('contract');root.SamasEditing.result(canonical({...v,schema:'i4b-write-result-v1',operation:operations.includes(v.operation)?'edit':v.operation}));return v;}
 const stateLabel=(locale,r)=>[r.reviewed?copy[locale].viewed:null,r.disposition==='deferred'?copy[locale].deferred:r.disposition==='needs-information'?copy[locale].needs:null].filter(Boolean).join(' · ')||copy[locale].unhandled;
 function createPanel({main,dialog,body,locale,close},personal){
  let footer=null,opener=null;
  const tr=k=>{const text=personal.copy(locale(),k)??root.SamasExplanations.copy[locale()]?.[k];if(typeof text!=='string')throw Error('Translation contract');return text;};
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  const button=(text,fn,cls)=>{const n=el('button',text,cls);n.type='button';n.addEventListener('click',fn);return n;};
  const title=row=>tr(row.step==='school-session'?'schoolTitle':row.step==='home-visit'?'visitTitle':'questionTitle');
  function dismiss(){dialog.classList.remove('i7-pending-dialog');delete document.documentElement.dataset.i7PendingOpen;footer=null;}
  dialog.addEventListener('close',()=>{if(dialog.open)return;dismiss();const target=opener;opener=null;if(target?.isConnected&&target.checkVisibility())target.focus();else main.focus();});
  function modal(text,row=null){
   const active=document.activeElement;if(active&&active!==document.body&&active!==main&&!dialog.contains(active))opener=active;
   body.replaceChildren();dialog.classList.add('i7-pending-dialog');document.documentElement.dataset.i7PendingOpen='true';
   const header=el('header',undefined,'i7-dialog-header'),summary=el('div');summary.append(el('small',tr('boundary')));
   const h=el('h2',text);h.id='dialog-title';summary.append(h);
   if(row)summary.append(el('p',row.supported_date===null?tr('noDate'):tr('date')+': '+row.supported_date,'i7-dialog-date'),el('p',personal.state(locale(),row),'i7-dialog-state'));
   const exit=button(tr('close'),close,'i7-dialog-close');header.append(summary,exit);
   const content=el('div',undefined,'i7-dialog-scroll');content.tabIndex=0;content.setAttribute('role','region');content.setAttribute('aria-label',tr('detailBody'));
   footer=el('footer',undefined,'i7-dialog-footer');footer.hidden=true;body.append(header,content,footer);
   if(!dialog.open)dialog.showModal();dialog.scrollTop=0;body.scrollTop=0;content.scrollTop=0;exit.focus();return content;
  }
  function attach(actions){footer.replaceChildren(actions);footer.hidden=false;}
  function overview(v,row,accept,review){
   const content=modal(title(row),row),what=el('section'),why=el('section'),next=el('section');
   what.append(el('h3',tr('what')),el('p',tr('source')),el('p',tr(v.step==='school-session'?'school':v.step==='home-visit'?'visit':'question')));
   why.append(el('h3',tr('why')),el('p',tr(v.action)));for(const reason of v.reasons)why.append(el('p',tr(reason)));
   why.append(el('p',tr(v.safety===null?'neutral':v.safety)),el('p',tr('unknownFacts')));
   next.append(el('h3',tr('next')),el('p',tr(v.can_accept?'candidate':'blocked')));content.append(what,why,next);
   const actions=el('div',undefined,'connection-actions');
   if(v.can_accept){const b=button(tr('preview'),accept,'primary');b.disabled=!!personal.isBlocked();actions.append(b);}
   if(row.can_review){const b=button(tr('recordHandling'),review);b.disabled=!!personal.isBlocked();actions.append(b);}
   if(actions.childElementCount)attach(actions);
  }
  function choose(row,actions){
   const content=modal(title(row),row);content.classList.add('personal-handling');
   const fieldset=el('fieldset'),legend=el('legend',tr('recordHandling'));fieldset.append(legend);
   for(const operation of operations){const label=el('label',undefined,'i7-handling-option'),radio=el('input');radio.type='radio';radio.name='personal-handling';radio.value=operation;radio.id='personal-'+operation;
    label.htmlFor=radio.id;const text=el('span');text.append(el('strong',tr(operation)),el('span',tr(operation+'Effect')));label.append(radio,text);fieldset.append(label);
    radio.addEventListener('change',()=>{if(radio.checked)actions.select(operation);});}
   const hint=el('p',tr('chooseHelp'),'i7-handling-status');hint.setAttribute('role','status');hint.setAttribute('aria-live','polite');
   content.append(el('p',tr('personalBoundary')),fieldset,hint);
   const controls=el('div',undefined,'connection-actions'),save=button(tr('savePersonal'),()=>actions.confirm(save),'primary');save.disabled=true;
   controls.append(button(tr('back'),actions.back),save);attach(controls);
   return {pending(){save.disabled=true;hint.textContent=tr('preparing');},ready(){save.disabled=false;hint.textContent=tr('ready');},failed(){save.disabled=true;hint.textContent=tr('previewFailed');}};
  }
  function legacy(row,accept,review){
   const content=modal(title(row),row);content.append(el('p',tr('legacyBoundary')),el('p',tr(row.can_accept?'candidate':'blocked')));
   const controls=el('div',undefined,'connection-actions');
   if(row.can_accept)controls.append(button(tr('preview'),accept,'primary'));
   if(row.can_review)controls.append(button(tr('recordHandling'),review));
   if(controls.childElementCount)attach(controls);
  }
  return {modal,footer:attach,dismiss,choose,details:overview,legacy,explanationModal:row=>modal(row?title(row):tr('detailTitle'),row)};
 }

 const editing=root.SamasEditing;
 if(editing){root.SamasEditing=Object.freeze({...editing,create(options){
  const extra=root.SamasI8;
  let state='all',member=null;const labels=(locale,k)=>extra?.copy[locale]?.[k]??copy[locale][k]??null,tr=k=>labels(options.locale(),k);
  const personal={operations:extra?.operations||operations,parse:extra?.parse||parse,preview:extra?.preview||preview,result:extra?.result||result,state:extra?.stateLabel||stateLabel,copy:labels,request:extra?.request};
  Object.assign(personal,createPanel(options,personal));
  if(extra?.choose)personal.choose=(row,actions)=>extra.choose({...options,personal},row,actions);
  const base=editing.create({...options,personal});
  return {...base,isPersonalOperation:operation=>personal.operations.includes(operation),pendingQuery:()=>state==='all'?'':'&state='+state,pendingState:()=>state,
   resetPendingFilter(){state='all';},resetSession(){state='all';member=null;base.resetSession();},bindMember(v){if(v!==member){state='all';member=v;}base.bindMember(v);},
   pendingControls(refresh){const controls=document.createElement('div');controls.className='i7-pending-filters';const wrap=document.createElement('label');wrap.textContent=tr('filter');wrap.htmlFor='pending-state';const select=document.createElement('select');select.id='pending-state';for(const s of extra?.states||states){const o=document.createElement('option');o.value=s;o.textContent=tr(s==='needs-information'?'needs':s);select.append(o);}select.value=state;select.addEventListener('change',()=>{if((extra?.states||states).includes(select.value)){state=select.value;refresh();}});controls.append(wrap,select);options.main.append(controls);},
   copy(k){if(extra?.feedback?.[k])return tr(extra.feedback[k]);return k==='review'?tr('reviewSaved'):k==='defer'?tr('deferSaved'):k==='needs-information'?tr('needsSaved'):base.copy(k);}};
 }});}
 root.SamasReviews=Object.freeze({copy,parse,preview,result,stateLabel,operations});
 if(typeof module!=='undefined')module.exports=root.SamasReviews;
})(globalThis);
