(function () {
  'use strict';
  // Fixed visual specimens, not an application model or an authorization snapshot.
  function freeze(value) {
    if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); }
    return value;
  }
  const specimens = freeze({
    tasks: [
      {id:'visit', title:'visit', assignee:'clara', status:'open', date:null},
      {id:'school', title:'school', assignee:'devon', status:'open', date:'2035-06-12'},
      {id:'finished-visit', title:'visit', assignee:'joint', status:'done', date:null}
    ],
    pending: [
      {id:'school-question', title:'schoolQuestion', description:'schoolQuestionBody', state:'decision'},
      {id:'repair-question', title:'repairQuestion', description:'repairQuestionBody', state:'information'},
      {id:'community-later', title:'laterQuestion', description:'laterQuestionBody', state:'later'}
    ]
  });
  const copy = freeze({
    'zh-CN': {
      home:'首页',tasks:'家庭待办',pending:'待确认',calendar:'日程',security:'安全中心',settings:'设置与隐私',offers:'优惠查询',
      proposal:'视觉提案 · 虚构数据 · 不保存',space:'家庭空间',viewer:'预览：Clara',more:'更多',language:'语言',
      sidebarNote:'仅供设计评审。未连接家庭账户或后端。',title:'Samas Family OS · UX2 视觉提案',nav:'主导航',
      welcome:'Clara，你好。',welcomeBody:'家里的待办和待确认，在这里一起理清。',homeEyebrow:'家庭总览',
      openCount:'待完成',pendingCount:'待确认',datedCount:'有日期',securityCount:'待核实',next:'接下来要做的',allTasks:'全部待办',
      together:'一起确认',allPending:'查看待确认',upcoming:'近期安排',dateType:'已接受待办的日期',fixedDate:'2035 年 6 月 · 固定虚构日期',
      securityHeading:'有一项信息，先核实再决定',securityBody:'暂时无法确认是否安全。请通过独立可信渠道核实，不使用可疑信息里的联系方式。',securityLink:'查看核实建议',
      tasksBody:'同一份家庭待办，分工清楚，彼此可见的范围保持不变。',taskTotal:'3 项固定样稿 · 非实时授权查询',
      all:'全部',mine:'我负责',theirs:'对方负责',jointFilter:'共同负责',filterFuture:'负责人筛选为未来布局示意，尚未接线。',
      clara:'Clara',devon:'Devon',joint:'共同负责',assignee:'负责人',open:'待完成',done:'已完成',noDate:'未设置日期',date:'日期',
      school:'安排学校活动',visit:'安排家庭到访',details:'详情',close:'关闭',cancel:'取消',
      pendingBody:'先弄清需要决定什么，再决定是否加入待办。',decision:'待决定',information:'需要更多信息',later:'稍后处理',
      schoolQuestion:'下一次学校活动，如何安排？',schoolQuestionBody:'已有活动安排依据，仍需明确接受。这项建议尚未成为家庭待办。',
      repairQuestion:'到访时间，还需要确认',repairQuestionBody:'缺少明确到访时间。先补齐信息，不将不确定内容当作已确认安排。',
      laterQuestion:'社区资料领取安排',laterQuestionBody:'这是延期状态的排版示例，事项仍未解决，不会自动提醒。',
      previewDecision:'查看确认样稿',previewInformation:'查看缺失信息',unresolved:'延期与需要更多信息都不是已完成；仅展示固定状态，不记录个人决定。',
      pendingPreview:'是否加入家庭待办？',pendingEffect:'正式流程须独立确认、重新授权并绑定当前信息版本。本页只展示确认布局，不创建任务。',
      missingTitle:'先补齐信息',missingBody:'尚无明确时间或充分行动依据。此处不提供加入待办操作，也不将审阅视为接受或安全解除。',
      detailNote:'分工只表示主负责成员，不改变共享范围。私人来源仍需独立授权。',
      choose:'选择负责人',assign:'调整分工',complete:'标记完成',reopen:'恢复未完成',detailPreview:'设计状态 · 不保存',
      candidateNote:'候选仅为排版示例；正式界面由服务端提供当前获准选项。',
      assignmentTitle:'确认调整分工',completeTitle:'确认标记完成',reopenTitle:'确认恢复未完成',before:'修改前',after:'修改后',
      assignEffect:'只改变这项任务的负责人，不改变共享范围，也不执行付款、预约或回复。',
      statusEffect:'只记录家庭任务的跟踪状态，不证明付款、预约或回复已完成。恢复未完成不撤回原接受。',
      confirmPreview:'预览效果',notSaved:'已展示确认效果；没有保存修改，任务保持原样。',cancelled:'已取消预览，没有保存任何修改。',
      designStates:'更多设计状态',unknownPreview:'查看结果未知样稿',emptyPreview:'查看空状态样稿',longPreview:'查看长标题样稿',controlsPreview:'查看控件样稿',inputLabel:'文本输入（仅样式）',
      unknown:'结果尚未确认',unknownBody:'状态样稿：不要重复提交。正式系统须核对原请求，不自动重发或更换请求身份。',check:'核对最近操作',
      checkBody:'此样稿没有请求或回执，不能核实任何结果，也不会执行重试。实际核对仍由现有后端控制。',
      returnTasks:'返回待办',empty:'这里暂时没有待办',emptyBody:'这是空状态设计示例。没有编造日期、提醒或替代任务。',
      longTitle:'整理学校活动中的无障碍通行、同行安排及需要双方另行确认的细节（长标题排版样例）',
      appearance:'外观',system:'跟随系统',light:'浅色',dark:'深色',appearanceBody:'只改变此标签页的视觉样式，刷新重置。不会改变权限或事项状态。',
      designBoundary:'独立视觉样稿',boundaryBody:'所有成员、任务和状态均为虚构。没有登录、授权服务、数据库或真实操作，静态文件不是隐私边界。',
      securityTitle:'先核实，再行动',securityPageBody:'以下为未知风险的设计状态，不是检测结果或安全保证。',
      securityDetail:'核实建议',securityDetailBody:'不要使用可疑消息提供的链接或号码。通过独立核验的官方渠道确认。没有隔离、恢复、发送或付款操作。',
      calendarBody:'只展示已经明确给出的日期，不推断“今天到期”。',
      offersBody:'优惠只在你主动查询时出现，不进入首页或待确认。',offerQuery:'查看优惠排版样稿',offerTitle:'虚构花园用品优惠',offerBody:'仅供按需信息的排版评审；未验证资格，不产生任务、提醒或购买。',
      noChanges:'浏览、取消和退出都不保存。',designLabel:'未来筛选布局',dateLabel:'6 月',juneDay:'12',
      calendarCaption:'不含优惠有效期，也未接入真实日历。',
      compareHome:'首页方案对比 · 仅样稿',a1:'A1 编辑式',a2:'A2 家庭中心',hubTitle:'我们的家庭事务',hubBody:'Clara & Devon',actionArea:'共同处理',acceptedSteps:'已加入待办',openQuestions:'还需确认',householdNotes:'其他安排',homeGuide:'两套方案使用相同数据，选择不保存。'
    },
    'en-US': {
      home:'Home',tasks:'Household tasks',pending:'Pending',calendar:'Calendar',security:'Security',settings:'Settings & privacy',offers:'Offers',
      proposal:'Design proposal · Fictional · No saving',space:'Household',viewer:'Preview: Clara',more:'More',language:'Language',
      sidebarNote:'Design review only. No household account or backend connection.',title:'Samas Family OS · UX2 design proposal',nav:'Main navigation',
      welcome:'Hello, Clara.',welcomeBody:'A shared place to understand tasks and open questions.',homeEyebrow:'AT HOME',
      openCount:'To do',pendingCount:'Pending',datedCount:'Dated',securityCount:'To verify',next:'What’s next',allTasks:'All tasks',
      together:'Decide together',allPending:'View Pending',upcoming:'Coming up',dateType:'Accepted task date',fixedDate:'June 2035 · Fixed fictional date',
      securityHeading:'One item to verify first',securityBody:'Safety cannot yet be established. Verify through an independent trusted channel, not contact details in the suspicious item.',securityLink:'View guidance',
      tasksBody:'One household list, clear responsibilities, unchanged sharing.',taskTotal:'3 fixed specimens · Not a live authorized query',
      all:'All',mine:'Mine',theirs:'Partner’s',jointFilter:'Joint',filterFuture:'Future assignment-filter layout only; not connected.',
      clara:'Clara',devon:'Devon',joint:'Jointly managed',assignee:'Assignee',open:'To do',done:'Completed',noDate:'No date set',date:'Date',
      school:'Arrange school session',visit:'Arrange home visit',details:'Details',close:'Close',cancel:'Cancel',
      pendingBody:'Understand the question before deciding to accept a task.',decision:'To decide',information:'More information',later:'Later',
      schoolQuestion:'How shall we arrange the next school session?',schoolQuestionBody:'Supporting arrangements exist, but explicit acceptance is still needed. This suggestion is not yet a household task.',
      repairQuestion:'The visit time needs clarification',repairQuestionBody:'An explicit visit time is missing. Seek more information without presenting uncertain details as a confirmed arrangement.',
      laterQuestion:'Community materials collection',laterQuestionBody:'A deferred-state layout specimen. It remains unresolved, with no automatic reminder.',
      previewDecision:'View confirmation design',previewInformation:'View missing information',unresolved:'Deferred and information-needed items remain unresolved. Fixed states only; no personal decisions are recorded.',
      pendingPreview:'Add a household task?',pendingEffect:'The real flow needs separate confirmation, current authorization and exact evidence binding. This layout creates no task.',
      missingTitle:'More information first',missingBody:'A clear time or supported obligation is missing. No acceptance control is offered; review is neither acceptance nor safety clearance.',
      detailNote:'Assignment identifies the lead member, without changing sharing. Private source access remains independently authorized.',
      choose:'Choose assignee',assign:'Change assignment',complete:'Mark completed',reopen:'Reopen task',detailPreview:'Design state · No saving',
      candidateNote:'Layout candidates only; the real service supplies currently authorized choices.',
      assignmentTitle:'Confirm assignment change',completeTitle:'Confirm completion',reopenTitle:'Confirm reopening',before:'Before',after:'After',
      assignEffect:'Changes the lead member only, not sharing. No payment, booking or reply is performed.',
      statusEffect:'Updates household tracking only, not proof of payment, booking or reply. Reopening does not undo acceptance.',
      confirmPreview:'Preview only',notSaved:'Confirmation appearance shown. No edit saved; tasks are unchanged.',cancelled:'Preview cancelled. No changes saved.',
      designStates:'More design states',unknownPreview:'View unknown-outcome design',emptyPreview:'View empty-state design',longPreview:'View long-title design',controlsPreview:'View control specimen',inputLabel:'Text input (appearance only)',
      unknown:'Outcome not yet confirmed',unknownBody:'State specimen: do not resubmit. The real system checks the original request, without blind retries or a replacement identity.',check:'Check latest operation',
      checkBody:'This preview has no request or receipt to verify and cannot retry anything. Real reconciliation remains controlled by the existing backend.',
      returnTasks:'Back to tasks',empty:'No tasks here yet',emptyBody:'An empty-state design specimen. No invented dates, reminders or replacement tasks.',
      longTitle:'Arrange accessible arrival, accompanying adults and details needing joint confirmation for the school session (long-title specimen)',
      appearance:'Appearance',system:'System',light:'Light',dark:'Dark',appearanceBody:'Visual changes stay in this tab and reset on refresh. Rights and item states never change.',
      designBoundary:'Independent visual proposal',boundaryBody:'All members, tasks and states are fictional. No login, authorization service, database or real actions. Static files are not a privacy boundary.',
      securityTitle:'Verify before acting',securityPageBody:'An unknown-risk design state, not a detector result or safety guarantee.',
      securityDetail:'Verification guidance',securityDetailBody:'Do not use links or phone numbers from the suspicious message. Verify through independently established official channels. No quarantine, restore, send or payment operations.',
      calendarBody:'Only dates explicitly supplied; no invented “due today” claims.',
      offersBody:'Offers appear only on request, never on Home or Pending.',offerQuery:'View offer layout specimen',offerTitle:'Fictional garden-supplies offer',offerBody:'On-demand information layout only. Eligibility unverified; no task, reminder or purchase.',
      noChanges:'Inspecting, cancelling and exiting never saves.',designLabel:'Future filter layout',dateLabel:'JUN',juneDay:'12',
      calendarCaption:'No offer-expiry dates or real calendar connection.',
      compareHome:'Home comparison · Design only',a1:'A1 Editorial',a2:'A2 Household Hub',hubTitle:'Our household',hubBody:'Clara & Devon',actionArea:'Shared actions',acceptedSteps:'Accepted tasks',openQuestions:'Open questions',householdNotes:'Around the household',homeGuide:'Same specimens in both designs. Selection is not saved.'
    }
  });
  if (Object.keys(copy['zh-CN']).sort().join() !== Object.keys(copy['en-US']).sort().join()) throw Error('Translation contract');
  if (typeof module !== 'undefined') module.exports = {specimens,copy};
  if (typeof document === 'undefined') return;
  let locale='zh-CN',view='home',bucket='decision',appearance='system',offersIntent=false,opener=null,homeDesign='a1';
  const media=matchMedia('(prefers-color-scheme: dark)'),small=matchMedia('(max-width:730px)');
  const main=document.getElementById('main'),dialog=document.getElementById('dialog'),content=document.getElementById('dialog-content');
  const tr=key=>{const value=copy[locale][key];if(typeof value!=='string')throw Error('Missing translation');return value;};
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  const button=(text,fn,cls)=>{const n=el('button',text,cls);n.type='button';n.addEventListener('click',fn);return n;};
  const person=value=>tr(value);
  const announce=key=>{document.getElementById('feedback').textContent=key?tr(key):'';};
  function theme(){document.documentElement.dataset.theme=appearance==='system'?(media.matches?'dark':'light'):appearance;}
  media.addEventListener('change',()=>{if(appearance==='system')theme();});theme();
  function close(){if(dialog.open)dialog.close();content.replaceChildren();if(opener?.isConnected)opener.focus();else main.focus();}
  dialog.addEventListener('cancel',event=>{event.preventDefault();close();announce('cancelled');});
  function navigate(next){close();view=next;document.getElementById('more').open=false;announce(null);render();main.focus();window.scrollTo({top:0,behavior:'instant'});}
  const paths={home:'M3 10 12 3l9 7v10H4V10m5 10v-7h6v7',tasks:'m4 7 2 2 4-4m3 2h7M4 17l2 2 4-4m3 2h7',pending:'M12 8v5m0 4h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18',calendar:'M4 6h16v15H4V6m3-3v6m10-6v6M4 11h16',security:'m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3m0 5v5m0 3h.01'};
  function icon(key){const n=document.createElementNS('http://www.w3.org/2000/svg','svg');n.setAttribute('viewBox','0 0 24 24');n.setAttribute('aria-hidden','true');n.classList.add('nav-icon');const p=document.createElementNS(n.namespaceURI,'path');p.setAttribute('d',paths[key]);n.append(p);return n;}
  const language=el('label',undefined,'language');language.append(el('span'));const languageSelect=el('select');languageSelect.id='language';
  for(const [value,label] of [['zh-CN','简体中文'],['en-US','English']]){const o=el('option',label);o.value=value;languageSelect.append(o);}language.append(languageSelect);
  languageSelect.addEventListener('change',()=>{close();locale=languageSelect.value==='en-US'?'en-US':'zh-CN';document.getElementById('more').open=false;announce(null);render();if(small.matches)document.getElementById('more-label').focus();else languageSelect.focus();});
  function placeLanguage(){document.getElementById(small.matches?'more-content':'desktop-language').append(language);}
  small.addEventListener('change',placeLanguage);
  function chrome(){
    document.documentElement.lang=locale;document.title=tr('title');
    for(const [id,key] of [['proposal-label','proposal'],['space-label','space'],['viewer','viewer'],['more-label','more'],['sidebar-note','sidebarNote']])document.getElementById(id).textContent=tr(key);
    language.firstChild.textContent=tr('language');languageSelect.setAttribute('aria-label',tr('language'));
    const nav=document.getElementById('navigation');nav.replaceChildren();nav.setAttribute('aria-label',tr('nav'));
    for(const key of ['home','tasks','pending','calendar','security']){const b=button('',()=>navigate(key));b.dataset.view=key;b.append(icon(key),el('span',tr(key)));if(key===view)b.setAttribute('aria-current','page');if(key==='pending')b.append(el('span','2','nav-count'));nav.append(b);}
    const secondary=document.getElementById('secondary'),more=document.getElementById('more-content');secondary.replaceChildren();more.replaceChildren();more.append(el('span',tr('viewer'),'viewer'));
    for(const key of ['offers','settings'])for(const host of [secondary,more])host.append(button(tr(key),()=>navigate(key)));
    placeLanguage();
  }
  function heading(title,body,eyebrow){const h=el('header',undefined,'page-heading');if(eyebrow)h.append(el('p',tr(eyebrow),'eyebrow'));h.append(el('h1',tr(title)));if(body)h.append(el('p',tr(body)));main.append(h);}
  function section(title,action){const s=el('section',undefined,'section'),head=el('div',undefined,'section-title');head.append(el('h2',tr(title)));if(action)head.append(button(tr(action[0]),()=>navigate(action[1]),'link'));s.append(head);return s;}
  function row(task){const n=el('article',undefined,'task-row'+(task.status==='done'?' completed':''));n.dataset.task=task.id;const text=el('div');text.append(el('span',tr(task.status),'tag'+(task.status==='open'?' action':'')),el('h3',tr(task.title)));const meta=el('div',undefined,'task-meta');meta.append(el('span',tr('assignee')+(locale==='zh-CN'?'：':': ')+person(task.assignee)),el('span',task.date||tr('noDate')));text.append(meta);n.append(text,button(tr('details'),()=>detail(task)));return n;}
  function taskList(tasks){const box=el('div',undefined,'surface task-list');tasks.forEach(t=>box.append(row(t)));return box;}
  function dateBlock(){const n=el('div',undefined,'date-block surface'),date=el('div',tr('juneDay'),'date-number');date.append(el('small',tr('dateLabel')));const text=el('div');text.append(el('h3',tr('school')),el('p',tr('dateType')),el('p','2035-06-12'));n.append(date,text);return n;}
  function homeSummary(){
    const summary=el('div',undefined,'home-index');summary.setAttribute('aria-label',tr('homeEyebrow'));
    for(const [number,label,target] of [[2,'openCount','tasks'],[2,'pendingCount','pending'],[1,'datedCount','calendar'],[1,'securityCount','security']]){
      const b=button('',()=>navigate(target));b.append(el('span',tr(label)),el('strong',String(number)));summary.append(b);
    }return summary;
  }
  function homeQuestion(){
    const teaser=el('article',undefined,'home-question');teaser.append(el('span',tr('decision'),'tag question'),el('h3',tr('schoolQuestion')),el('p',tr('schoolQuestionBody')),button(tr('previewDecision'),pendingPreview));return teaser;
  }
  function homeSafety(){
    const s=el('section',undefined,'home-safety');s.append(el('span',tr('securityCount'),'tag question'),el('h3',tr('securityHeading')),el('p',tr('securityBody')),button(tr('securityLink'),()=>navigate('security'),'link'));return s;
  }
  function home(){
    const home=el('div',undefined,'home-design '+homeDesign);home.dataset.design=homeDesign;
    const compare=el('div',undefined,'home-comparison'),label=el('span',tr('compareHome'));
    compare.setAttribute('role','group');compare.setAttribute('aria-label',tr('compareHome'));compare.append(label);
    for(const key of ['a1','a2']){const b=button(tr(key),()=>{homeDesign=key;render();main.querySelector('[data-design-choice="'+key+'"]').focus();});b.dataset.designChoice=key;b.setAttribute('aria-pressed',String(homeDesign===key));compare.append(b);}
    home.append(compare);
    const greeting=el('header',undefined,'home-greeting');greeting.append(el('p',tr(homeDesign==='a1'?'homeEyebrow':'hubBody'),'eyebrow'),el('h1',tr(homeDesign==='a1'?'welcome':'hubTitle')));home.append(greeting);
    const grid=el('div',undefined,'home-layout'),primary=el('div',undefined,'home-primary'),support=el('aside',undefined,'home-support');
    if(homeDesign==='a1'){
      const tasks=section('next',['allTasks','tasks']);tasks.append(taskList(specimens.tasks.filter(t=>t.status==='open')));primary.append(tasks);
      const questions=section('together',['allPending','pending']);questions.append(homeQuestion());primary.append(questions);
      support.append(homeSummary());const dates=section('upcoming',['calendar','calendar']);dates.append(dateBlock(),el('p',tr('fixedDate'),'page-note'));support.append(dates,homeSafety());
    }else{
      const actions=section('actionArea',['allTasks','tasks']);actions.classList.add('action-board');
      actions.append(el('p',tr('acceptedSteps'),'board-caption'),taskList(specimens.tasks.filter(t=>t.status==='open')),el('p',tr('openQuestions'),'board-caption'),homeQuestion());primary.append(actions);
      const notes=section('householdNotes');const questions=el('div',undefined,'hub-question-entry');questions.append(el('h3',tr('together')),el('p',tr('repairQuestion')),button(tr('allPending'),()=>navigate('pending')));notes.append(questions,dateBlock(),button(tr('calendar'),()=>navigate('calendar'),'link'));support.append(notes,homeSafety());
      home.append(homeSummary());
    }
    grid.append(primary,support);home.append(grid,el('p',tr('homeGuide'),'home-guide'));main.append(home);
  }
  function designTools(){const d=el('details',undefined,'design-tools');d.append(el('summary',tr('designStates')));const actions=el('div',undefined,'actions');actions.append(button(tr('emptyPreview'),emptyPreview),button(tr('longPreview'),()=>detail({...specimens.tasks[1],title:'longTitle'})),button(tr('unknownPreview'),unknownPreview),button(tr('controlsPreview'),controlsPreview));d.append(actions);main.append(d);}
  function tasks(){heading('tasks','tasksBody');const filters=el('div',undefined,'filter-proposal');filters.setAttribute('role','group');filters.setAttribute('aria-label',tr('designLabel'));for(const key of ['all','mine','theirs','jointFilter']){const b=button(tr(key),()=>{});b.disabled=true;filters.append(b);}main.append(filters,el('p',tr('filterFuture'),'caption'),taskList(specimens.tasks),el('p',tr('taskTotal'),'page-note'));designTools();}
  function pending(){heading('pending','pendingBody');const tabs=el('div',undefined,'buckets');for(const [key,count] of [['decision',2],['later',1]]){const b=button(tr(key)+' '+count,()=>{bucket=key;render();main.querySelector('.buckets button[aria-pressed="true"]').focus();});b.setAttribute('aria-pressed',String(bucket===key));tabs.append(b);}main.append(tabs);
    for(const p of specimens.pending.filter(p=>bucket==='later'?p.state==='later':p.state!=='later')){const n=el('article',undefined,'pending-item'+(p.state==='information'?' needs-info':''));n.append(el('span',tr(p.state),'tag question'),el('h3',tr(p.title)),el('p',tr(p.description)));n.append(button(tr(p.state==='decision'?'previewDecision':p.state==='later'?'details':'previewInformation'),p.state==='decision'?pendingPreview:p.state==='later'?()=>{modal('laterQuestion');content.append(el('p',tr('laterQuestionBody')));}:missingPreview));main.append(n);}main.append(el('p',tr('unresolved'),'page-note'));
  }
  function settings(){heading('settings');const group=el('section',undefined,'surface settings-group'),label=el('label',tr('appearance'));label.htmlFor='appearance';const select=el('select');select.id='appearance';for(const key of ['system','light','dark']){const o=el('option',tr(key));o.value=key;select.append(o);}select.value=appearance;select.addEventListener('change',()=>{if(['system','light','dark'].includes(select.value)){appearance=select.value;theme();}});group.append(label,select,el('p',tr('appearanceBody')));const boundary=el('section',undefined,'settings-group');boundary.append(el('h2',tr('designBoundary')),el('p',tr('boundaryBody')));main.append(group,boundary);}
  function render(){chrome();main.replaceChildren();main.dataset.view=view;
    if(view==='home')home();else if(view==='tasks')tasks();else if(view==='pending')pending();else if(view==='settings')settings();
    else if(view==='calendar'){heading('calendar','calendarBody');main.append(dateBlock(),el('p',tr('calendarCaption'),'page-note'));}
    else if(view==='security'){heading('securityTitle','securityPageBody');const note=el('div',undefined,'unknown-strip');note.append(el('strong',tr('unknown')),el('p',tr('securityBody')),button(tr('securityDetail'),()=>{modal('securityDetail');content.append(el('p',tr('securityDetailBody')));}));main.append(note);}
    else if(view==='offers'){heading('offers','offersBody');if(!offersIntent)main.append(button(tr('offerQuery'),()=>{offersIntent=true;render();}));else{const n=el('article',undefined,'surface settings-group');n.append(el('h2',tr('offerTitle')),el('p',tr('offerBody')));main.append(n);}}
  }
  function modal(key){if(!dialog.open)opener=document.activeElement;content.replaceChildren();const top=el('div',undefined,'dialog-top'),dismiss=button(tr('close'),()=>{close();announce('cancelled');});top.append(el('small',tr('detailPreview')),dismiss);const h=el('h2',tr(key));h.id='dialog-title';content.append(top,h);if(!dialog.open)dialog.showModal();dismiss.focus();}
  function detail(task){modal(task.title);const facts=el('div',undefined,'detail-meta');for(const [label,value] of [['assignee',person(task.assignee)],['date',task.date||tr('noDate')]]){const d=el('div');d.append(el('span',tr(label)),el('strong',value));facts.append(d);}content.append(el('span',tr(task.status),'tag'),facts,el('p',tr('detailNote'),'detail-help'));
    const assignment=el('div',undefined,'assignment'),label=el('label',tr('choose'));label.htmlFor='assignee';const select=el('select');select.id='assignee';for(const key of ['clara','devon','joint']){const o=el('option',person(key));o.value=key;select.append(o);}select.value=task.assignee;assignment.append(label,select);
    const actions=el('div',undefined,'actions'),assign=button(tr('assign'),()=>editPreview(task,'assign',select.value));assign.disabled=true;select.addEventListener('change',()=>{assign.disabled=!['clara','devon','joint'].includes(select.value)||select.value===task.assignee;});actions.append(assign,button(tr(task.status==='done'?'reopen':'complete'),()=>editPreview(task,task.status==='done'?'reopen':'complete')));content.append(assignment,actions,el('p',tr('candidateNote'),'detail-help'));
  }
  function previewFooter(){const actions=el('div',undefined,'dialog-actions');actions.append(button(tr('cancel'),()=>{close();announce('cancelled');}),button(tr('confirmPreview'),()=>{close();announce('notSaved');},'primary'));content.append(actions);}
  function editPreview(task,action,assignee){modal(action==='assign'?'assignmentTitle':action==='complete'?'completeTitle':'reopenTitle');content.append(el('h3',tr(task.title)));const diff=el('div',undefined,'change-preview');for(const [label,value] of [['before',person(task.assignee)+' · '+tr(task.status)],['after',person(action==='assign'?assignee:task.assignee)+' · '+tr(action==='complete'?'done':action==='reopen'?'open':task.status)]]){const r=el('div');r.append(el('span',tr(label)),el('strong',value));diff.append(r);}content.append(diff,el('p',tr(action==='assign'?'assignEffect':'statusEffect')));previewFooter();}
  function pendingPreview(){modal('pendingPreview');const facts=el('div',undefined,'detail-meta');for(const [label,value] of [['assignee',person('joint')],['date','2036-03-14']]){const n=el('div');n.append(el('span',tr(label)),el('strong',value));facts.append(n);}content.append(el('h3',tr('schoolQuestion')),facts,el('p',tr('pendingEffect')));previewFooter();}
  function missingPreview(){modal('missingTitle');content.append(el('p',tr('missingBody')));}
  function emptyPreview(){modal('emptyPreview');const box=el('div',undefined,'empty');box.append(el('h3',tr('empty')),el('p',tr('emptyBody')));content.append(box);}
  function controlsPreview(){modal('controlsPreview');const field=el('div',undefined,'assignment'),label=el('label',tr('inputLabel'));label.htmlFor='sample-input';const input=el('input');input.id='sample-input';input.type='text';input.value='Clara';input.readOnly=true;field.append(label,input);content.append(field,el('p',tr('noChanges'),'detail-help'));}
  function unknownPreview(){modal('unknown');const strip=el('div',undefined,'unknown-strip');strip.append(el('p',tr('unknownBody')),button(tr('check'),()=>{modal('check');content.append(el('p',tr('checkBody')),button(tr('returnTasks'),()=>{close();navigate('tasks');}));}));content.append(strip);}
  render();
})();
