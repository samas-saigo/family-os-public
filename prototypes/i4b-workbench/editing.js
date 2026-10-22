(function(root){
  'use strict';
  const zh={notice:'本地后端连接测试 · 虚构数据 · 确认后保存',readonly:'本轮支持接受、分工及完成状态；不执行外部活动。',
    details:'详情',close:'关闭',cancel:'取消',confirm:'确认修改',assign:'调整分工',complete:'标记完成',reopen:'恢复未完成',choose:'选择负责人',
    preview:'确认修改家庭待办',effect:'只修改这条共享任务的分工或跟踪状态，不扩大共享权限，不执行付款、预约或回复。恢复未完成不会撤回原接受。',
    loading:'正在核对当前权限与任务。',failed:'当前无法准备操作。未提交修改；如先前提交中断，请先核对最近操作。',
    submitting:'正在提交。关闭窗口不会撤回请求。',unknown:'结果尚未确认。不要重复提交，请核对最近操作。',recover:'核对最近操作',
    notApplied:'已核实本次请求未生效。请重新读取，再独立确认。',stale:'任务或权限已变化。请重新读取，再独立确认。',
    unavailable:'当前权限或信息不支持此操作。',conflict:'请求内容冲突，请核对原请求。',none:'本会话没有待核对的操作。',committed:'已核实保存，正在重新读取。',
    before:'修改前',after:'修改后',pendingState:'待完成',completed:'已完成',total:'当前可查看',empty:'当前没有可查看的待确认事项。',
    question:'需要更多信息',blocked:'暂不能接受；仍需核实信息。',accept:'加入家庭待办',acceptPreview:'确认加入家庭待办',acceptConfirm:'确认接受',
    acceptEffect:'确认后创建一项共享家庭待办，并移出待确认。不执行预约、付款或其他外部活动。',
    assignee:'负责人',assignmentHelp:'负责人表示当前主负责成员，不改变这项待办的共享范围。',operationStatus:'操作核对',
    joint:'共同负责',clara:'Clara',devon:'Devon',date:'日期',noDate:'未设置日期',school:'安排学校活动',visit:'安排家庭到访'};
  const en={notice:'Local backend test · Fictional data · Confirm to save',readonly:'Acceptance, assignment and tracking status only; no external execution.',
    details:'Details',close:'Close',cancel:'Cancel',confirm:'Confirm change',assign:'Change assignment',complete:'Mark completed',reopen:'Reopen task',choose:'Choose assignee',
    preview:'Confirm household task change',effect:'Changes only this shared task’s assignment or tracking status. No sharing expansion, payment, booking or reply. Reopening does not undo acceptance.',
    loading:'Checking current rights and task.',failed:'Operation unavailable. No edit submitted; check the latest operation if a prior submission was interrupted.',
    submitting:'Submitting. Closing does not withdraw the request.',unknown:'Outcome unknown. Do not resubmit; check the latest operation.',recover:'Check latest operation',
    notApplied:'Verified not applied. Reload, then confirm independently.',stale:'Task or rights changed. Reload, then confirm independently.',
    unavailable:'Current rights or information do not support this operation.',conflict:'Changed-intent conflict. Check the original request.',none:'No operation to check in this session.',committed:'Save verified; reloading.',
    before:'Before',after:'After',pendingState:'Pending',completed:'Completed',total:'Currently available',empty:'No Pending items are currently available to you.',
    question:'More information needed',blocked:'Not eligible for acceptance; more verification needed.',accept:'Add household task',acceptPreview:'Confirm household task',acceptConfirm:'Confirm acceptance',
    acceptEffect:'Creates one shared household task and removes the proposal from Pending. No booking, payment or other external activity.',
    assignee:'Assignee',assignmentHelp:'Assignment identifies the lead member; it does not change who can view this task.',operationStatus:'Operation check',
    joint:'Jointly managed',clara:'Clara',devon:'Devon',date:'Date',noDate:'No date set',school:'Arrange school session',visit:'Arrange home visit'};
  if(Object.keys(zh).sort().join()!==Object.keys(en).sort().join())throw Error('Translation contract');
  const keys=(v,k)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).sort().join()===k.split(',').sort().join();
  const handle=v=>typeof v==='string'&&/^[0-9a-f]{32}$/.test(v);
  const assignee=v=>['joint','i2-clara','i2-devon'].includes(v);
  const state=v=>['pending','completed'].includes(v);
  function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
  function decode(raw){if(typeof raw!=='string'||raw.length>16384||/[^\x20-\x7e]/.test(raw))throw Error('contract');const v=JSON.parse(raw);if(canonical(v)!==raw)throw Error('contract');return v;}
  function task(r){
    if(!keys(r,'id,step,assignee,status,approved_date,revision,can_edit')||typeof r.can_edit!=='boolean')throw Error('contract');
    const {can_edit,...base}=r;
    SamasTaskContract.parse(canonical({schema:'i3-fictional-task-page-v1',synthetic_only:true,pagination:{limit:1,offset:0},tasks:{items:[base],total:1,has_more:false}}),1,0);
    return r;
  }
  function taskParse(raw,limit,offset,expected=null){const v=decode(raw);
    if(expected!==null){
      if(!keys(expected,'responsibility,step')||!['all','mine','other','joint'].includes(expected.responsibility)||
        ![null,'school-session','home-visit'].includes(expected.step)||v.schema!=='i4b-task-page-v2'||
        !keys(v,'schema,synthetic_only,pagination,tasks,query')||!keys(v.query,'responsibility,step')||
        v.query.responsibility!==expected.responsibility||v.query.step!==expected.step)throw Error('contract');
    }else if(v.schema!=='i4b-task-page-v1'||Object.hasOwn(v,'query'))throw Error('contract');
    if(!Array.isArray(v.tasks?.items))throw Error('contract');
    for(const r of v.tasks.items)task(r);
    const {query,...envelope}=v;
    const base={...envelope,schema:'i3-fictional-task-page-v1',tasks:{...v.tasks,items:v.tasks.items.map(({can_edit,...r})=>r)}};
    SamasTaskContract.parse(canonical(base),limit,offset);return v;
  }
  function options(raw,id){const v=decode(raw);if(!keys(v,'schema,synthetic_only,draft,task,assignees')||v.schema!=='i4b-edit-options-v1'||v.synthetic_only!==true||!handle(v.draft)||task(v.task).id!==id||!v.task.can_edit||!Array.isArray(v.assignees)||v.assignees.length<1||v.assignees.length>3||new Set(v.assignees).size!==v.assignees.length||!v.assignees.every(assignee))throw Error('contract');return v;}
  function preview(raw,id){const v=decode(raw);if(!keys(v,'schema,synthetic_only,receipt,task,action,assignee,status')||v.schema!=='i4b-edit-preview-v1'||v.synthetic_only!==true||!handle(v.receipt)||task(v.task).id!==id||!v.task.can_edit||!assignee(v.assignee)||!state(v.status)||!['assign','complete','reopen'].includes(v.action)||
    (v.action==='assign'&&(v.status!==v.task.status||v.assignee===v.task.assignee))||
    (v.action!=='assign'&&(v.assignee!==v.task.assignee||v.status===v.task.status||v.status!==(v.action==='complete'?'completed':'pending'))))throw Error('contract');return v;}
  function result(raw){const v=decode(raw);if(!keys(v,'schema,synthetic_only,outcome,receipt,operation')||v.schema!=='i4b-write-result-v1'||v.synthetic_only!==true||!['accept','edit',null].includes(v.operation))throw Error('contract');
    const {operation,...base}=v;SamasAcceptance.result(canonical({...base,schema:'i4a-acceptance-result-v1'}));
    if((v.receipt===null)!==(v.operation===null))throw Error('contract');return v;
  }
  function create({main,dialog,body,api,locale,close,committed,refresh,pendingDetails=null,pendingPreview=null,personal=null}){
    let current=null,inspected=null,attempt=null,epoch=0,sessionEpoch=0,lastMember=null,recovering=false;
    let content=body,reviewForm=null,reviewChoice=0;
    const tr=k=>{const v=personal?.copy(locale(),k)??(locale()==='zh-CN'?zh:en)[k];if(typeof v!=='string')throw Error('Translation contract');return v;};
    const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
    const button=(text,fn)=>{const n=el('button',text);n.type='button';n.addEventListener('click',fn);return n;};
    const person=v=>tr(v==='joint'?'joint':v==='i2-clara'?'clara':'devon');
    const tracking=v=>tr(v==='completed'?'completed':'pendingState');
    const title=r=>tr(r.step==='school-session'?'school':r.step==='home-visit'?'visit':'question');
    const readResult=personal?.result||result;
    const blocked=()=>attempt&&(attempt.outcome==='submitting'||attempt.message==='unknown');
    if(personal)personal.isBlocked=blocked;
    function dismiss(){epoch++;reviewChoice++;current=null;inspected=null;reviewForm=null;personal?.dismiss?.();}
    function modal(text){if(personal?.modal&&inspected?.kind==='pending'){content=personal.modal(text);return;}content=body;body.replaceChildren();const top=el('div',undefined,'dialog-top'),dismiss=button(tr('close'),()=>{close();main.focus();});top.append(el('small',tr('notice')),dismiss);const h=el('h2',text);h.id='dialog-title';content.append(top,h);if(!dialog.open)dialog.showModal();dismiss.focus();}
    function status(){
      const previous=main.querySelector('.acceptance-status');
      if(!['home','tasks','pending'].includes(main.dataset.view)){previous?.remove();return;}
      const signature=JSON.stringify([locale(),attempt,recovering]);
      if(previous?.dataset.signature===signature)return;
      previous?.remove();
      const box=el('section',undefined,'acceptance-status edit-operation-status');box.dataset.signature=signature;box.setAttribute('role','status');box.setAttribute('aria-live','polite');
      const text=el('div');text.append(el('strong',tr('operationStatus')));
      if(attempt)text.append(el('p',tr(attempt.message)));box.append(text);
      const check=button(tr('recover'),recover);check.disabled=recovering||attempt?.outcome==='submitting';box.append(check);main.append(box);
    }
    function render(p){main.append(el('p',tr('total')+'：'+p.total));if(!p.items.length)main.append(el('p',tr('empty'),'empty'));
      const rows=el('div',undefined,'cards wide');for(const r of p.items){const card=el('article',undefined,'card');card.dataset.pending=r.id;
        card.append(el('h3',title(r)),el('p',r.supported_date||tr('noDate')));if(!r.can_accept)card.append(el('p',tr('blocked')));
        if(personal)card.append(el('p',personal.state(locale(),r),'personal-state'));
        card.append(button(tr(pendingDetails?'details':r.can_accept?'accept':'details'),()=>pendingDetails?pendingDetails(r):openPending(r)));rows.append(card);}main.append(rows);status();}
    async function openPending(row){
      if(row.can_accept&&blocked()){status();return;}close();inspected={id:row.id,revision:row.revision,kind:'pending'};
      const request=epoch,identity=sessionEpoch;modal(title(row));if(!row.can_accept){content.append(el('p',tr('blocked')));return;}
      content.append(el('p',tr('loading')));
      try{const p=SamasAcceptance.preview(await (pendingPreview?pendingPreview(row):api('/api/pending/preview',true,{id:row.id})),row.id);
        if(request!==epoch||identity!==sessionEpoch)return;if(pendingPreview&&p.revision!==row.revision)throw Error('contract');current={...p,operation:'accept'};modal(tr('acceptPreview'));
        content.append(el('h3',title(p)),el('p',person(p.assignee)),el('p',p.approved_date||tr('noDate')),el('p',tr('acceptEffect')));confirmation(current);
      }catch(_){if(request===epoch&&identity===sessionEpoch){modal(tr('acceptPreview'));content.append(el('p',tr('failed')));}}
    }
    async function taskDetail(row){
      close();inspected={id:row.id,revision:row.revision,kind:'tasks',canEdit:row.can_edit};const request=epoch,identity=sessionEpoch;
      modal(title(row));taskSummary(row);
      if(!row.can_edit||blocked())return;
      content.append(el('p',tr('loading')));
      try{const p=options(await api('/api/tasks/edit-options',true,{id:row.id}),row.id);
        if(request!==epoch||identity!==sessionEpoch)return;
        if(p.task.revision!==row.revision)throw Error('contract');
        modal(title(row));taskSummary(row);
        const label=el('label',tr('choose'));label.htmlFor='edit-assignee';const select=el('select');select.id='edit-assignee';
        if(!p.assignees.includes(p.task.assignee)){const value=el('option',person(p.task.assignee));value.value=p.task.assignee;value.disabled=true;select.append(value);}
        for(const a of p.assignees){const o=el('option',person(a));o.value=a;select.append(o);}
        select.value=p.task.assignee;
        const assign=button(tr('assign'),()=>prepare(p,'assign',select.value));assign.disabled=true;
        select.addEventListener('change',()=>{assign.disabled=!p.assignees.includes(select.value)||select.value===p.task.assignee;});
        const assignment=el('div',undefined,'task-edit-assignment');assignment.append(label,select);
        const actions=el('div',undefined,'connection-actions task-edit-actions');
        actions.append(assign,button(tr(row.status==='completed'?'reopen':'complete'),()=>prepare(p,row.status==='completed'?'reopen':'complete')));
        content.append(assignment,actions);
      }catch(_){if(request===epoch&&identity===sessionEpoch){modal(title(row));content.append(el('p',tr('failed')));}}
    }
    function taskSummary(row){content.append(el('p',tr('assignee')+(locale()==='zh-CN'?'：':': ')+person(row.assignee),'task-current-assignee'),
      el('p',tr('assignmentHelp'),'task-assignment-help'),el('p',tracking(row.status)),el('p',row.approved_date||tr('noDate')));}
    async function prepare(draft,action,assignee){
      if(blocked())return;const request=epoch,identity=sessionEpoch;modal(tr('preview'));content.append(el('p',tr('loading')));
      try{const p=preview(await api('/api/tasks/edit-preview',true,{draft:draft.draft,action,...(action==='assign'?{assignee}:{})}),draft.task.id);
        if(request!==epoch||identity!==sessionEpoch)return;
        if(p.action!==action||(action==='assign'&&p.assignee!==assignee))throw Error('contract');
        current={...p,operation:'edit'};modal(tr(action));content.append(el('h3',title(p.task)),el('p',tr('before')+'：'+person(p.task.assignee)+' · '+tracking(p.task.status)),
          el('p',tr('after')+'：'+person(p.assignee)+' · '+tracking(p.status)),el('p',tr('effect')));confirmation(current);
      }catch(_){if(request===epoch&&identity===sessionEpoch){modal(tr('preview'));content.append(el('p',tr('failed')));}}
    }
    function reviewActions(row){
      const section=el('section',undefined,'personal-handling');section.append(el('h3',tr('handling')),el('p',personal.state(locale(),row)),el('p',tr('personalBoundary')));
      if(row.can_review){const actions=el('div',undefined,'connection-actions');for(const op of personal.operations){const b=button(tr(op),()=>openReview(row,op));b.disabled=!!blocked();actions.append(b);}section.append(actions);}return section;
    }
    function personalDetail(row,back=null){if(blocked())return;close();inspected={id:row.id,revision:row.revision,kind:'pending',canReview:row.can_review};if(personal.legacy&&!back){personal.legacy(row,()=>openPending(row),()=>personalDetail(row,()=>personalDetail(row)));return;}if(personal.choose){reviewForm=personal.choose(row,{back:()=>{if(back)back();else personalDetail(row);},select:(operation,reason)=>openReview(row,operation,reason),confirm:control=>{if(current&&personal.operations.includes(current.operation))submit(current,control);}});return;}modal(title(row));content.append(el('p',row.supported_date||tr('noDate')),reviewActions(row));if(row.can_accept)content.append(button(tr('accept'),()=>openPending(row)));}
    async function openReview(row,operation,reason=null){
      if(!personal||blocked()||!row.can_review)return;
      if(personal.choose&&reviewForm){
        const form=reviewForm,choice=++reviewChoice,request=epoch,identity=sessionEpoch;current=null;form.pending();
        const payload=personal.request?personal.request(row,operation,reason):{id:row.id,revision:row.revision,operation};
        if(payload===null){form.waiting?.();return;}
        try{const p=personal.preview(await api('/api/pending/review-preview',true,payload),row,operation,reason);
          if(form!==reviewForm||choice!==reviewChoice||request!==epoch||identity!==sessionEpoch)return;
          current=p;form.ready(p);
        }catch(_){if(form===reviewForm&&choice===reviewChoice&&request===epoch&&identity===sessionEpoch)form.failed();}
        return;
      }
      close();inspected={id:row.id,revision:row.revision,kind:'pending',canReview:row.can_review};
      const request=epoch,identity=sessionEpoch;modal(tr(operation));content.append(el('p',tr('loading')));
      try{const p=personal.preview(await api('/api/pending/review-preview',true,{id:row.id,revision:row.revision,operation}),row,operation);
        if(request!==epoch||identity!==sessionEpoch)return;current=p;modal(tr(operation));content.append(el('h3',title(row)),el('p',tr(operation+'Effect')),el('p',tr('personalBoundary')));confirmation(current);
      }catch(_){if(request===epoch&&identity===sessionEpoch){modal(tr(operation));content.append(el('p',tr('failed')));}}
    }
    function confirmation(p){const actions=el('div',undefined,'connection-actions');const control=button(tr(personal?.operations.includes(p.operation)?'savePersonal':p.operation==='accept'?'acceptConfirm':'confirm'),()=>submit(p,control));control.className='primary';actions.append(control,button(tr('cancel'),()=>{close();main.focus();}));if(personal?.footer&&inspected?.kind==='pending')personal.footer(actions);else content.append(actions);}
    async function submit(p,control){
      if(current!==p||blocked())return;const identity=sessionEpoch;control.disabled=true;
      attempt={receipt:p.receipt,operation:p.operation,action:p.action,outcome:'submitting',message:'submitting'};current=null;
      modal(tr('submitting'));let value;
      try{value=readResult(await api(personal?.operations.includes(p.operation)?'/api/pending/review-confirm':p.operation==='edit'?'/api/tasks/edit-confirm':'/api/pending/accept',true,{receipt:p.receipt,confirm:true}));
        if(value.receipt!==p.receipt||value.operation!==p.operation)throw Error('contract');}
      catch(_){value={receipt:p.receipt,operation:p.operation,outcome:'UNKNOWN-reconciliation-required'};}
      if(identity===sessionEpoch)finish(value);
    }
    function finish(value){
      const success=['COMMITTED','COMMITTED-replay'].includes(value.outcome);
      const message=success?'committed':value.outcome==='UNKNOWN-reconciliation-required'?'unknown':value.outcome==='NOT_APPLIED-stale'?'stale':value.outcome==='NOT_APPLIED-unavailable'?'unavailable':value.outcome==='NOT_APPLIED-changed-intent'?'conflict':value.receipt===null?'none':'notApplied';
      attempt={...value,message};close();
      if(success){attempt=null;committed(value.operation);}else refresh();
    }
    async function recover(){
      if(recovering||attempt?.outcome==='submitting')return;const identity=sessionEpoch;recovering=true;status();let v;
      try{const r=attempt?.receipt,op=attempt?.operation;v=readResult(await api(r?(personal?.operations.includes(op)?'/api/pending/review-outcome':op==='edit'?'/api/tasks/edit-outcome':'/api/pending/outcome'):'/api/writes/recover',true,r?{receipt:r}:{}));
        if(r&&(v.receipt!==r||v.operation!==op))throw Error('contract');}
      catch(_){v={outcome:'UNKNOWN-reconciliation-required',receipt:attempt?.receipt||null,operation:attempt?.operation||null};}
      if(identity!==sessionEpoch)return;recovering=false;finish(v);
    }
    function revalidate(p){if(inspected?.kind==='pending'){const r=p?.items.find(r=>r.id===inspected.id);if(!r||r.revision!==inspected.revision||(inspected.canReview!==undefined&&r.can_review!==inspected.canReview)||(current&&!personal?.operations.includes(current.operation)&&!r.can_accept))close();}}
    function revalidateTasks(p){if(inspected?.kind==='tasks'){const r=p?.items.find(r=>r.id===inspected.id);if(!r||r.revision!==inspected.revision||r.can_edit!==inspected.canEdit)close();}}
    function resetSession(){sessionEpoch++;dismiss();attempt=null;recovering=false;lastMember=null;}
    function bindMember(v){if(lastMember!==v){resetSession();lastMember=v;}}
    return {render,openPending,reviewActions:personal?reviewActions:null,personalDetail,parse:personal?.parse||SamasAcceptance.parse,taskParse,taskDetail,revalidate,revalidateTasks,dismiss,resetSession,bindMember,status,copy:k=>personal?.copy(locale(),k)??(Object.hasOwn(zh,k)?tr(k):null)};
  }
  root.SamasEditing=Object.freeze({create,taskParse,options,preview,result});
  if(typeof module!=='undefined')module.exports=root.SamasEditing;
})(globalThis);
