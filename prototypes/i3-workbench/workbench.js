(function(){
  'use strict';
  const zh={home:'首页',tasks:'家庭待办',pending:'待确认',upcoming:'日程',security:'安全中心',information:'信息',offers:'优惠查询',settings:'设置与隐私',more:'更多',language:'语言',currentMember:'当前成员',updated:'家庭待办已更新',accepted:'已加入家庭待办',notice:'本地后端连接测试 · 虚构数据 · 只读',
    loading:'正在读取家庭待办。',access:'无法验证当前会话或访问权限。请检查本地测试服务。',connection:'连接失败或超时，未显示旧任务。',contract:'任务数据格式不匹配，未显示任何任务。',
    session:'建立虚构测试会话',intro:'在此浏览器发起请求，再由启动终端核对编号并批准 Clara 或 Devon。不是生产登录。',start:'发起请求',cancel:'取消请求',waiting:'等待终端批准，配对两分钟后失效。',retry:'重新读取',logout:'注销测试会话',loggedOut:'测试会话已注销。',unknown:'注销结果无法确认，请关闭本地测试服务，不要自动重试。',cancelled:'请求已取消。',
    overview:'家庭总览',todo:'任务总数',dates:'有日期',verify:'待核实',unsupported:'本轮未连接此功能，不显示离线演示内容。',taskEmpty:'当前没有可查看的家庭待办。',empty:'当前没有可查看的家庭待办。',responsibility:'负责人筛选',responsibilityAll:'全部',mine:'我负责',other:'对方负责',filteredEmpty:'没有符合当前筛选条件的家庭待办。',all:'全部类型',school:'安排学校活动',visit:'安排家庭到访',joint:'共同负责',clara:'Clara',devon:'Devon',pendingState:'待完成',completed:'已完成',date:'已批准日期',noDate:'未设置日期',details:'详情',close:'关闭',tracking:'完成仅表示家庭跟踪状态，不代表外部活动已执行。',next:'下一页',previous:'上一页',total:'当前可查看',recent:'近期安排',calendar:'本轮未连接日历，请以待办中明确批准的日期为准。',appearance:'外观',system:'跟随系统',light:'浅色',dark:'深色',readonly:'当前为只读连接。确认、分工、完成及归档操作尚未开放。'};
  const en={home:'Home',tasks:'Household tasks',pending:'Pending',upcoming:'Calendar',security:'Security',information:'Information',offers:'Offers',settings:'Settings & privacy',more:'More',language:'Language',currentMember:'Current member',updated:'Household task updated',accepted:'Added to household tasks',notice:'Local backend test · Fictional data · Read only',
    loading:'Loading household tasks.',access:'Current session or access could not be verified. Check the local test service.',connection:'Connection failed or timed out. Previous tasks are not displayed.',contract:'Task data contract mismatch. No tasks are displayed.',
    session:'Establish fictional test session',intro:'Request access in this browser, then have the startup terminal match the ID and approve Clara or Devon. Not production login.',start:'Request session',cancel:'Cancel request',waiting:'Awaiting terminal approval. Pairing expires in two minutes.',retry:'Reload',logout:'Log out test session',loggedOut:'Test session logged out.',unknown:'Logout outcome is unknown. Close the local test service; do not automatically retry.',cancelled:'Request cancelled.',
    overview:'Household overview',todo:'Tracked tasks',dates:'Dated',verify:'To verify',unsupported:'Not connected in this slice. Offline demo content is not substituted.',taskEmpty:'No household tasks are currently available to you.',empty:'No household tasks are currently available to you.',responsibility:'Responsibility',responsibilityAll:'All',mine:'Mine',other:'Partner’s',filteredEmpty:'No household tasks match these filters.',all:'All types',school:'Arrange school session',visit:'Arrange home visit',joint:'Jointly managed',clara:'Clara',devon:'Devon',pendingState:'Pending',completed:'Completed',date:'Approved date',noDate:'No date set',details:'Details',close:'Close',tracking:'Completion records household tracking only, not external execution.',next:'Next page',previous:'Previous page',total:'Currently available',recent:'Upcoming',calendar:'Calendar is not connected. Only explicitly approved task dates are displayed.',appearance:'Appearance',system:'System',light:'Light',dark:'Dark',readonly:'Read-only connection. Acceptance, assignment, completion and archive are unavailable.'};
  if(Object.keys(zh).sort().join()!==Object.keys(en).sort().join())throw Error('Translation contract');
  // Connected A1 copy only; identity and both collections still come from the server.
  const homeCopy={
    'zh-CN':{welcome:'欢迎回来',homeTasks:'家庭待办',allTasks:'查看全部家庭待办',homePending:'待你确认',allPending:'查看待确认',eligible:'可进入确认流程',unverified:'仍需核实',pageScope:'本页任务',summaryScope:'待确认摘要',of:' / ',availableTasks:'当前可查看任务',availablePending:'当前可查看待确认',approvedDates:'本页已批准日期',homeDate:'已批准日期',securityTitle:'安全中心',dateMeaning:'日期来自本页任务，不代表截止期限或日历预约。',emptyDates:'本页任务未设置日期。',emptyPending:'当前没有可查看的待确认事项。',notConnected:'当前未连接',securityLink:'进入安全中心',securityNote:'尚未连接安全事件，不表示已完成安全检查。'},
    'en-US':{welcome:'Welcome back',homeTasks:'Household tasks',allTasks:'View all household tasks',homePending:'For your confirmation',allPending:'View Pending',eligible:'Confirmation available',unverified:'More verification needed',pageScope:'Tasks on this page',summaryScope:'Pending summary',of:' / ',availableTasks:'Authorized tasks',availablePending:'Authorized Pending',approvedDates:'Approved dates on this page',homeDate:'Approved date',securityTitle:'Security',dateMeaning:'Dates belong to tasks on this page, not deadlines or calendar bookings.',emptyDates:'No dates set for tasks on this page.',emptyPending:'No Pending items are currently available to you.',notConnected:'Not connected',securityLink:'Open Security',securityNote:'Security events are not connected. No safety check is implied.'}
  };
  if(Object.keys(homeCopy['zh-CN']).sort().join()!==Object.keys(homeCopy['en-US']).sort().join())throw Error('Translation contract');
  let locale='zh-CN',view='home',offset=0,step='',responsibility='all',filterMember=null,member=null,current=null,state='loading',ticket=null,opened=null,sequence=0,poll,pairingAvailable=true,sessionFlight=null,acceptance=null;
  const limit=12;
  const i9=()=>view==='home'&&document.documentElement.dataset.i9==='true';
  const a1=()=>view==='home'&&!i9()&&document.documentElement.dataset.connection==='i4b';
  const ht=k=>{const value=homeCopy[locale][k];if(typeof value!=='string')throw Error('Translation contract');return value;};
  const main=document.getElementById('main'),dialog=document.getElementById('detail-dialog'),body=document.getElementById('dialog-body');
  const tr=k=>{const override=acceptance?.copy(k);const value=override===null||override===undefined?(locale==='zh-CN'?zh:en)[k]:override;if(typeof value!=='string')throw Error('Translation contract');return value;};
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  const button=(text,fn,cls)=>{const n=el('button',text,cls);n.type='button';n.addEventListener('click',fn);return n;};
  const media=matchMedia('(prefers-color-scheme: dark)');let appearance='system';
  function theme(){document.documentElement.dataset.theme=appearance==='system'?(media.matches?'dark':'light'):appearance;}
  media.addEventListener('change',()=>{if(appearance==='system')theme();});theme();
  function placeLanguage(){const small=matchMedia('(max-width:730px)').matches;const label=document.getElementById('language-label');if(small)document.getElementById('secondary-body').append(label);else document.querySelector('.preferences').insertBefore(label,document.getElementById('reload'));}
  addEventListener('resize',placeLanguage);placeLanguage();
  function announce(key){const n=document.getElementById('feedback');n.textContent=key?tr(key):'';n.dataset.active=key?'true':'false';}
  function closeDetail(){opened=null;dialog.close();body.replaceChildren();acceptance?.dismiss();}
  function navigate(next){acceptance?.resetPendingFilter?.();view=next;offset=0;step='';responsibility='all';closeDetail();document.getElementById('secondary-menu').open=false;announce(null);const reading=refresh();main.focus();return reading;}
  // Presentation only. Existing mounted buttons/handlers and all request state stay intact.
  function navLabel(b,text){
    const paths={home:'M3 10 12 3l9 7v10H4V10m5 10v-7h6v7',tasks:'m4 7 2 2 4-4m3 2h7M4 17l2 2 4-4m3 2h7',pending:'M12 8v5m0 4h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18',upcoming:'M4 6h16v15H4V6m3-3v6m10-6v6M4 11h16',security:'m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3m0 5v5m0 3h.01'};
    if(document.documentElement.dataset.connection!=='i4b'){b.textContent=text;return;}
    if(b.dataset.view===view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');
    if(!paths[b.dataset.view]){b.textContent=text;return;}
    if(!b.firstElementChild){const icon=document.createElementNS('http://www.w3.org/2000/svg','svg'),path=document.createElementNS(icon.namespaceURI,'path');
      icon.setAttribute('viewBox','0 0 24 24');icon.setAttribute('aria-hidden','true');icon.setAttribute('focusable','false');icon.classList.add('connected-nav-icon');path.setAttribute('d',paths[b.dataset.view]);icon.append(path);b.append(icon,el('span'));}
    b.lastElementChild.textContent=text;
  }
  function chrome(){
    document.documentElement.lang=locale;
    document.getElementById('notice').textContent=tr('notice');document.getElementById('more-label').textContent=tr('more');
    document.getElementById('language-text').textContent=tr('language');document.getElementById('language').setAttribute('aria-label',tr('language'));
    document.getElementById('member-label').textContent=tr('currentMember');
    document.getElementById('session-member').hidden=member===null;document.getElementById('reload').textContent=tr('retry');
    document.getElementById('member-status').textContent=member===null?'':(member==='i2-clara'?'Clara':'Devon');
    const nav=document.getElementById('navigation');
    if(!nav.firstChild){const group=el('div',undefined,'nav-main');
      for(const key of ['home','tasks','pending','upcoming','security']){const b=button('',()=>navigate(key));b.dataset.view=key;group.append(b);}nav.append(group);
      const secondary=document.getElementById('secondary-body');
      for(const key of ['information','offers','settings']){const b=button('',()=>navigate(key));b.dataset.view=key;secondary.prepend(b);}
    }
    for(const b of document.querySelectorAll('button[data-view]')){navLabel(b,tr(b.dataset.view));b.classList.toggle('active',b.dataset.view===view);}
  }
  function title(){const row=el('div',undefined,'connection-heading');
    const greeting=a1()&&state==='active'&&member!==null;
    const name=member==='i2-clara'?'Clara':'Devon';
    row.append(el('h1',i9()&&globalThis.SamasActionHome?SamasActionHome.copy[locale].title:greeting?(locale==='zh-CN'?name+'，'+ht('welcome'):ht('welcome')+', '+name):tr(view==='home'?'overview':view)));main.append(row);}
  function detail(row){
    if(acceptance?.taskDetail){opened=null;acceptance.taskDetail(row);return;}
    opened=row.id;
    // Keep the modal and its Close control mounted during successful revalidation.
    if(!body.firstChild){const top=el('div',undefined,'dialog-top');top.append(el('small'),button('',()=>{closeDetail();main.focus();}));
      body.append(top,el('div',undefined,'detail-content'));}
    body.firstChild.firstChild.textContent=tr('notice');body.firstChild.lastChild.textContent=tr('close');
    const content=body.lastChild;content.replaceChildren();
    const h=el('h2',tr(row.step==='school-session'?'school':'visit'));h.id='dialog-title';
    content.append(h,el('p',tr(row.status==='completed'?'completed':'pendingState')),el('p',tr(row.assignee==='joint'?'joint':row.assignee==='i2-clara'?'clara':'devon')),
      el('p',row.approved_date===null?tr('noDate'):tr('date')+'：'+row.approved_date),el('p',tr('tracking'),'note-box'),el('p',tr('readonly')));
    if(!dialog.open)dialog.showModal();
  }
  dialog.addEventListener('cancel',event=>{event.preventDefault();closeDetail();main.focus();});
  function cards(){
    const p=current.tasks;
    if(!p.items.length){
      main.append(el('p',tr(view==='tasks'&&(step||responsibility!=='all')?'filteredEmpty':'taskEmpty'),'empty'));
      // A current grant/assignment change can empty a later filtered page.
      if(offset>0&&document.documentElement.dataset.connection==='i4b'){
        const pager=el('div',undefined,'connection-paging');pager.append(button(tr('previous'),()=>{offset=Math.max(0,offset-limit);refresh();}));main.append(pager);
      }return;
    }
    const rows=el('div',undefined,'cards wide');
    for(const r of p.items){const c=el('article',undefined,'card task-line');
      const row=el('div',undefined,'row');row.append(el('span',tr(r.status==='completed'?'completed':'pendingState'),'badge neutral'));
      const meta=el('div',undefined,'meta');meta.append(el('span',tr(r.assignee==='joint'?'joint':r.assignee==='i2-clara'?'clara':'devon')));
      if(r.approved_date!==null)meta.append(el('span',tr('date')+'：'+r.approved_date));
      c.append(row,el('h3',tr(r.step==='school-session'?'school':'visit')),meta,button(tr('details'),async()=>{opened=r.id;await refresh();}));rows.append(c);
    }main.append(rows);
    const pager=el('div',undefined,'connection-paging');
    if(offset>0)pager.append(button(tr('previous'),()=>{offset=Math.max(0,offset-limit);refresh();}));
    if(p.has_more)pager.append(button(tr('next'),()=>{offset+=limit;refresh();}));main.append(pager);
  }
  function editorialHome(){
    const shell=el('div',undefined,'a1-home'),layout=el('div',undefined,'a1-layout'),primary=el('div'),support=el('aside',undefined,'a1-support');
    const section=(key)=>{const s=el('section',undefined,'a1-section');s.append(el('h2',ht(key)));return s;};
    const taskName=r=>tr(r.step==='school-session'?'school':'visit');
    const inspect=r=>async()=>{opened=r.id;await refresh();};
    const tasks=section('homeTasks'),rows=el('div',undefined,'a1-task-list');
    tasks.append(el('p',ht('pageScope')+': '+current.tasks.items.length+ht('of')+current.tasks.total,'a1-caption'));
    // Stable within-page prioritization only; total includes completed, and other pages are not inferred.
    for(const r of [...current.tasks.items].sort((x,y)=>(x.status==='completed')-(y.status==='completed'))){
      const c=el('article',undefined,'a1-task');c.dataset.task=r.id;
      const text=el('div');text.append(el('span',tr(r.status==='completed'?'completed':'pendingState'),'a1-state'),el('h3',taskName(r)));
      const meta=el('div',undefined,'a1-meta');meta.append(el('span',tr('assignee')+(locale==='zh-CN'?'：':': ')+tr(r.assignee==='joint'?'joint':r.assignee==='i2-clara'?'clara':'devon')),
        el('span',r.approved_date===null?tr('noDate'):ht('homeDate')+': '+r.approved_date));text.append(meta);
      c.append(text,button(tr('details'),inspect(r)));rows.append(c);
    }
    if(!current.tasks.items.length)rows.append(el('p',tr('empty'),'a1-caption'));
    tasks.append(rows,button(ht('allTasks'),()=>navigate('tasks'),'a1-entry'));primary.append(tasks);
    const pending=section('homePending'),sample=current.pending.items.slice(0,3);
    pending.append(el('p',ht('summaryScope')+': '+sample.length+ht('of')+current.pending.total,'a1-caption'));
    if(!sample.length)pending.append(el('p',ht('emptyPending'),'a1-caption'));
    for(const r of sample){const row=el('div',undefined,'a1-question');row.dataset.homePending=r.id;
      row.append(el('h3',tr(r.step==='school-session'?'school':r.step==='home-visit'?'visit':'question')),
        el('p',ht(r.can_accept?'eligible':'unverified'),'a1-caption'));pending.append(row);}
    pending.append(button(ht('allPending'),()=>navigate('pending'),'a1-entry'));primary.append(pending);
    const counts=el('div',undefined,'a1-index');
    for(const [key,value,destination] of [['availableTasks',current.tasks.total,'tasks'],['availablePending',current.pending.total,'pending']]){
      const b=button('',()=>navigate(destination),'stat');b.dataset.homeCount=destination;b.append(el('span',ht(key)),el('strong',String(value)));counts.append(b);
    }support.append(counts);
    const dates=section('approvedDates'),dated=current.tasks.items.filter(r=>r.approved_date!==null).sort((x,y)=>x.approved_date.localeCompare(y.approved_date)||x.id.localeCompare(y.id));
    for(const r of dated){const entry=el('div',undefined,'a1-date');entry.append(el('time',r.approved_date),el('h3',taskName(r)),button(tr('details'),inspect(r)));dates.append(entry);}
    if(!dated.length)dates.append(el('p',ht('emptyDates'),'a1-caption'));
    dates.append(el('p',ht('dateMeaning'),'a1-caption'));support.append(dates);
    const security=section('securityTitle');security.append(el('p',ht('notConnected'),'a1-caption'),el('p',ht('securityNote'),'a1-caption'),button(tr('security'),()=>navigate('security'),'a1-entry'));support.append(security);
    layout.append(primary,support);shell.append(layout);main.append(shell);
  }
  function render(){
    chrome();if(globalThis.SamasActionHome)main.removeAttribute('aria-busy');main.dataset.view=view;main.replaceChildren();title();
    if(state!=='active'){
      main.append(el('p',tr(state),'connection-status'));
      if(state!=='loading'&&(ticket||pairingAvailable)){
        const panel=el('section',undefined,'connection-panel');panel.append(el('h2',tr('session')),el('p',tr('intro')));
        const actions=el('div',undefined,'connection-actions');
        if(ticket){panel.append(el('code',ticket));actions.append(button(tr('cancel'),()=>sessionAction('cancel')));}
        else actions.append(button(tr('start'),()=>sessionAction('start')));
        panel.append(actions);main.append(panel);
      }return;
    }
    if(view==='settings'){
      const label=el('label',tr('appearance'));label.htmlFor='appearance';const select=el('select');select.id='appearance';
      for(const option of ['system','light','dark']){const o=el('option',tr(option));o.value=option;select.append(o);}select.value=appearance;
      select.addEventListener('change',()=>{if(['system','light','dark'].includes(select.value)){appearance=select.value;theme();}});
      main.append(label,select,el('p',tr('readonly')),button(tr('logout'),()=>sessionAction('logout')));return;
    }
    if(view==='pending'&&acceptance){
      if(current){acceptance.pendingControls?.(()=>{offset=0;refresh();});acceptance.render(current.pending);}else main.append(el('p',tr('loading')));
      const pager=el('div',undefined,'connection-paging');
      if(offset>0)pager.append(button(tr('previous'),()=>{offset=Math.max(0,offset-limit);refresh();}));
      if(current?.pending.has_more)pager.append(button(tr('next'),()=>{offset+=limit;refresh();}));main.append(pager);return;
    }
    if(!['home','tasks'].includes(view)){main.append(el('p',tr('unsupported'),'empty'));return;}
    if(!current){main.append(el('p',tr('loading')));return;}
    if(i9()){SamasActionHome.render({main,home:current.home,locale,navigate,inspect:inspectHome});return;}
    if(a1()){editorialHome();return;}
    if(view==='home'){
      const stats=el('div',undefined,'stats');
      for(const [key,value,destination] of [['todo',current.tasks.total,'tasks'],['pending','—','pending'],['dates','—','upcoming'],['verify','—','security']]){
        const b=button('',()=>navigate(destination),'stat');b.append(el('strong',String(value)),el('span',tr(key)));stats.append(b);
      }main.append(stats);
      const columns=el('div',undefined,'columns');const left=el('section');left.append(el('h2',tr('tasks')));const right=el('section');right.append(el('h2',tr('recent')),el('p',tr('calendar'),'empty'));
      columns.append(left,right);main.append(columns);
      const before=Array.from(main.children);cards();for(const n of Array.from(main.children))if(!before.includes(n))left.append(n);
    }else{
      if(document.documentElement.dataset.connection==='i4b'){
        const group=el('div',undefined,'responsibility-filters');group.setAttribute('role','group');group.setAttribute('aria-label',tr('responsibility'));
        for(const [value,key] of [['all','responsibilityAll'],['mine','mine'],['other','other'],['joint','joint']]){
          const b=button(tr(key),async()=>{responsibility=value;offset=0;closeDetail();await refresh();if(view==='tasks'&&state==='active'&&responsibility===value)main.querySelector('[data-responsibility="'+value+'"]')?.focus();});
          b.dataset.responsibility=value;b.setAttribute('aria-pressed',String(responsibility===value));group.append(b);
        }main.append(group);
      }
      const filter=el('div',undefined,'connection-filter');const select=el('select');select.setAttribute('aria-label',tr('all'));
      for(const [value,key] of [['','all'],['school-session','school'],['home-visit','visit']]){const option=el('option',tr(key));option.value=value;select.append(option);}select.value=step;
      select.addEventListener('change',()=>{step=select.value;offset=0;refresh();});filter.append(select,el('span',tr('total')+'：'+current.tasks.total));main.append(filter);cards();
    }
  }
  async function inspectHome(id,kind){
    // Re-read current authority before navigation; never use the displayed card as a lease.
    if(!i9()||main.getAttribute('aria-busy')==='true')return;
    const actor=member,reading=refresh(true),request=sequence;await reading;
    if(request!==sequence||!i9()||state!=='active'||member!==actor)return;
    const rows=kind==='task'?current?.tasks.items:current?.pending.items;
    const row=rows?.find(r=>r.id===id);if(!row)return;
    if(kind==='task')detail(row);else acceptance?.inspectPending?.(row,kind==='followup');
  }
  async function api(path,post=true,values={}){
    let response;try{response=await fetch(path,{method:post?'POST':'GET',credentials:'same-origin',mode:'same-origin',cache:'no-store',redirect:'error',signal:AbortSignal.timeout(5000),
      headers:post?{'Content-Type':'application/json','X-Samas-Intent':'local-session'}:{'Accept':'application/json','X-Samas-Intent':'local-session'},...(post?{body:JSON.stringify(values)}:{})});}catch(_){throw Error('connection');}
    if(!response.ok)throw Error('access');
    if(response.headers.get('content-type')!=='application/json')throw Error('contract');
    const reader=response.body.getReader();const chunks=[];let size=0;
    try{for(let reads=0;;reads++){
      const part=await reader.read();if(part.done)break;size+=part.value.length;
      if(size>16384||reads>=64){await reader.cancel();throw Error('contract');}chunks.push(part.value);
    }}catch(error){throw Error(error.message==='contract'?'contract':'connection');}
    const bytes=new Uint8Array(size);let pos=0;for(const part of chunks){bytes.set(part,pos);pos+=part.length;}
    try{return new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch(_){throw Error('contract');}
  }
  async function refresh(automatic=false){
    const request=++sequence;clearTimeout(poll);const oldOpened=opened;
    const signature=()=>JSON.stringify([locale,view,member,current]);
    const previous=signature(),oldRow=current?.tasks?.items.find(r=>r.id===oldOpened);
    // Retain the already displayed DOM only during a bounded background check.
    // This never skips authorization: every failure below clears it immediately.
    const background=automatic===true&&state==='active';
    if(i9()&&globalThis.SamasActionHome)SamasActionHome.checking(main,true);
    if(!background){announce(null);current=null;member=null;state='loading';ticket=null;dialog.close();body.replaceChildren();acceptance?.dismiss();render();}
    let phase='session';
    try{
      // Coalesce only concurrently in-flight status/one-time claims, never cache results.
      // Every Tasks GET still performs its own current T1 authorization transaction.
      if(!sessionFlight)sessionFlight=api('/api/session').finally(()=>{sessionFlight=null;});
      const raw=await sessionFlight;const session=JSON.parse(raw);if(request!==sequence)return;
      if(session.state==='waiting'&&Object.keys(session).sort().join()==='request_id,state'&&/^[0-9a-f]{16}$/.test(session.request_id)){
        current=null;member=null;state='waiting';ticket=session.request_id;closeDetail();render();poll=setTimeout(refresh,2000);return;
      }
      if(session.state!=='active'||Object.keys(session).sort().join()!=='member,state'||!['i2-clara','i2-devon'].includes(session.member))throw Error('contract');
      acceptance?.bindMember(session.member);pairingAvailable=false;phase='tasks';
      if(filterMember!==session.member){responsibility='all';step='';offset=0;filterMember=session.member;}
      if(background&&member!==session.member){current=null;member=null;closeDetail();state='loading';render();}
      let next=null;
      if(i9()){
        if(!globalThis.SamasActionHome)throw Error('contract');
        const data=await api('/api/action-home',false);if(request!==sequence)return;
        try{next=SamasActionHome.parse(data,session.member);}catch(_){throw Error('contract');}
      }else if(['home','tasks'].includes(view)){
        const expected=view==='tasks'&&document.documentElement.dataset.connection==='i4b'?{responsibility,step:step||null}:null;
        const data=await api('/api/tasks?limit='+limit+'&offset='+offset+(step?'&step='+step:'')+(expected?'&responsibility='+expected.responsibility:''),false);
        if(request!==sequence)return;
        try{next=(acceptance?.taskParse||SamasTaskContract.parse)(data,limit,offset,expected);}catch(_){throw Error('contract');}
      }
      if(view==='pending'&&acceptance){
        const raw=await api('/api/pending?limit='+limit+'&offset='+offset+(acceptance.pendingQuery?.()||''),false);if(request!==sequence)return;
        try{next=acceptance.parse(raw,limit,offset,acceptance.pendingState?.());}catch(_){throw Error('contract');}
      }
      if(a1()){
        const raw=await api('/api/pending?limit='+limit+'&offset=0',false);if(request!==sequence)return;
        let pending;try{pending=acceptance.parse(raw,limit,0);}catch(_){throw Error('contract');}
        // Publish the pair only after BOTH strict reads and a fresh member check.
        // This is bounded sequential authorization, not a DB-atomic combined snapshot.
        phase='session';const latest=JSON.parse(await api('/api/session'));if(request!==sequence)return;
        if(latest.state!=='active'||Object.keys(latest).sort().join()!=='member,state'||latest.member!==session.member)throw Error('access');
        next={...next,pending:pending.pending};phase='home';
      }
      current=next;member=session.member;state='active';ticket=null;
      if(!background||previous!==signature())render();
      if(i9())SamasActionHome.checking(main,false);else if(globalThis.SamasActionHome)main.removeAttribute('aria-busy');
      if(oldOpened&&opened===oldOpened){const row=current?.tasks?.items.find(r=>r.id===oldOpened);
        if(row){if(!dialog.open||JSON.stringify(oldRow)!==JSON.stringify(row))detail(row);}
        else{closeDetail();}
      }
      if((view==='pending'||a1()||i9())&&acceptance)acceptance.revalidate(current?.pending);
      if(['home','tasks'].includes(view))acceptance?.revalidateTasks?.(current?.tasks);
      acceptance?.status?.();
      poll=setTimeout(()=>refresh(true),5000);
    }catch(error){
      if(request!==sequence)return;
      if(phase==='session'&&['access','contract'].includes(error.message)){acceptance?.resetSession();responsibility='all';filterMember=null;step='';offset=0;}
      if(phase==='session'&&error.message==='access')pairingAvailable=true;
      announce(null);current=null;member=null;closeDetail();state=['connection','contract','access'].includes(error.message)?error.message:'contract';render();
    }
  }
  async function sessionAction(action){
    acceptance?.resetSession();announce(null);responsibility='all';filterMember=null;step='';offset=0;
    const request=++sequence;clearTimeout(poll);current=null;member=null;ticket=null;closeDetail();state='loading';render();
    try{const value=JSON.parse(await api('/api/'+action));
      if(request!==sequence)return;
      if(action==='start'&&value.state==='waiting')return refresh();
      const expected=action==='cancel'?'cancelled':value.state==='unknown'?'unknown':'logged_out';
      if(value.state!==expected||Object.keys(value).join()!=='state')throw Error('contract');pairingAvailable=expected!=='unknown';state=expected==='logged_out'?'loggedOut':expected;render();
    }catch(error){if(request!==sequence)return;state=['connection','access'].includes(error.message)?error.message:'contract';render();}
  }
  const writeUI=document.documentElement.dataset.connection==='i4b'?globalThis.SamasEditing:document.documentElement.dataset.connection==='i4a'?globalThis.SamasAcceptance:null;
  if(writeUI){
    acceptance=writeUI.create({main,dialog,body,api,locale:()=>locale,close:closeDetail,
      committed:async(operation)=>{const personal=acceptance.isPersonalOperation?acceptance.isPersonalOperation(operation):['review','defer','needs-information'].includes(operation);await navigate(personal?'pending':'tasks');if(state==='active')announce(personal?operation:operation==='edit'?'updated':'accepted');},refresh});
  }
  document.getElementById('reload').addEventListener('click',()=>refresh());
  document.getElementById('language').addEventListener('change',event=>{locale=event.target.value==='en-US'?'en-US':'zh-CN';document.getElementById('secondary-menu').open=false;refresh();
    if(matchMedia('(max-width:730px)').matches)document.querySelector('#secondary-menu>summary').focus();else event.target.focus();});
  addEventListener('pagehide',()=>{++sequence;clearTimeout(poll);current=null;member=null;closeDetail();state='loading';render();});
  addEventListener('pageshow',e=>{if(e.persisted)refresh();});
  refresh();
})();
