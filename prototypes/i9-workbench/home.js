(function(root){
  'use strict';
  const regions=['mine','decisions','followup','collaboration'];
  const copy={
    'zh-CN':{title:'我的家庭行动',mine:'我的已确认待办',decisions:'待我确认',followup:'后续跟进',collaboration:'家庭协作',tasks:'查看全部家庭待办',pending:'查看全部待确认',emptyMine:'目前没有由你负责的未完成待办。',emptyDecisions:'目前没有需要你决定的事项。',emptyFollowup:'目前没有后续跟进事项。',emptyCollaboration:'目前没有可查看的协作待办。',noDate:'日期未提供',details:'详情',school:'安排学校活动',visit:'安排家庭到访',question:'待确认的家庭事项',assignee:'负责人',joint:'共同负责','my-task':'由你负责的已确认家庭待办。','joint-task':'你们共同负责的已确认家庭待办。','other-task':'你有权查看的另一成员待办。',undecided:'需要你作出明确决定。','viewed-undecided':'你已查看，但尚未作出决定。',deferred:'你选择了稍后处理。','needs-information':'你正在等待补充信息。'},
    'en-US':{title:'My household actions',mine:'My confirmed tasks',decisions:'For my decision',followup:'Follow-up',collaboration:'Household collaboration',tasks:'View all household tasks',pending:'View all Pending',emptyMine:'No unfinished tasks assigned to you.',emptyDecisions:'Nothing currently needs your decision.',emptyFollowup:'No follow-up items at present.',emptyCollaboration:'No collaboration tasks currently available to you.',noDate:'Date not provided',details:'Details',school:'Arrange school session',visit:'Arrange home visit',question:'Household question',assignee:'Assignee',joint:'Jointly managed','my-task':'A confirmed household task assigned to you.','joint-task':'A confirmed household task you manage jointly.','other-task':'Another member’s task you are authorized to view.',undecided:'Your explicit decision is needed.','viewed-undecided':'You viewed this but have not made a decision.',deferred:'You chose to handle this later.','needs-information':'You are waiting for more information.'}
  };
  if(Object.keys(copy['zh-CN']).sort().join()!==Object.keys(copy['en-US']).sort().join())throw Error('Translation contract');
  const keys=(v,k)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).sort().join()===k.split(',').sort().join();
  function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
  function parse(raw,member){
    if(typeof raw!=='string'||raw.length>16384||/[^\x20-\x7e]/.test(raw))throw Error('contract');
    const v=JSON.parse(raw);
    if(canonical(v)!==raw||!keys(v,'schema,synthetic_only,member,sections')||v.schema!=='i9-personal-action-home-v1'||v.synthetic_only!==true||!['i2-clara','i2-devon'].includes(v.member)||v.member!==member||!keys(v.sections,regions.join(',')))throw Error('contract');
    const ids=new Set();
    for(const name of regions){const s=v.sections[name],task=['mine','collaboration'].includes(name);
      if(!keys(s,'total,items')||!Number.isSafeInteger(s.total)||s.total<0||s.total>1000000||!Array.isArray(s.items)||s.items.length!==Math.min(3,s.total))throw Error('contract');
      let previous=null;
      for(const c of s.items){if(!keys(c,'item,reason'))throw Error('contract');const r=c.item;
        if(task){
          root.SamasEditing.taskParse(canonical({schema:'i4b-task-page-v1',synthetic_only:true,pagination:{limit:1,offset:0},tasks:{items:[r],total:1,has_more:false}}),1,0);
          const expected=r.assignee==='joint'?'joint-task':r.assignee===member?'my-task':'other-task';
          if(r.status!=='pending'||c.reason!==expected||(name==='collaboration')!==(expected==='other-task'))throw Error('contract');
        }else{
          root.SamasI8.parse(canonical({schema:'i8-personal-pending-page-v1',synthetic_only:true,query:{state:'all',step:null},pagination:{limit:1,offset:0},pending:{items:[r],total:1,has_more:false}}),1,0);
          const expected=r.disposition==='active'?(r.reviewed?'viewed-undecided':'undecided'):r.disposition;
          if(!r.can_review||!['active','deferred','needs-information'].includes(r.disposition)||c.reason!==expected||(name==='decisions')!==(r.disposition==='active'))throw Error('contract');
        }
        if(ids.has(r.id))throw Error('contract');ids.add(r.id);
        const day=task?r.approved_date:r.supported_date;
        const order=[day===null?'9999-99-99':day,...(task?[]:[r.reviewed?'1':'0']),r.id].join('|');
        if(previous!==null&&order<=previous)throw Error('contract');previous=order;
      }
    }
    // These fragments are ONLY for existing detail revalidation, never pagination/counts.
    return {home:v,tasks:{items:[...v.sections.mine.items,...v.sections.collaboration.items].map(c=>c.item)},pending:{items:[...v.sections.decisions.items,...v.sections.followup.items].map(c=>c.item)}};
  }
  function checking(main,value){main.setAttribute('aria-busy',String(value));for(const b of main.querySelectorAll('[data-i9-open]'))b.setAttribute('aria-disabled',String(value));}
  function render({main,home,locale,navigate,inspect}){
    const tr=k=>{const v=copy[locale]?.[k];if(typeof v!=='string')throw Error('Translation contract');return v;};
    const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
    const button=(text,fn)=>{const b=el('button',text);b.type='button';b.addEventListener('click',()=>{if(main.getAttribute('aria-busy')!=='true')fn();});return b;};
    const totals=el('div',undefined,'i9-totals');
    for(const key of regions.slice(0,3)){const b=button('',()=>document.getElementById('i9-'+key)?.scrollIntoView({block:'start',behavior:'instant'}));b.append(el('strong',String(home.sections[key].total)),el('span',tr(key)));totals.append(b);}main.append(totals);
    for(const name of regions){const s=home.sections[name],task=['mine','collaboration'].includes(name),section=el('section',undefined,'i9-section');section.id='i9-'+name;section.dataset.region=name;
      const heading=el('div',undefined,'i9-section-heading'),title=el('h2',tr(name));title.append(el('span',String(s.total),'i9-count'));
      heading.append(title,button(tr(task?'tasks':'pending'),()=>navigate(task?'tasks':'pending')));section.append(heading);
      if(!s.items.length)section.append(el('p',tr({mine:'emptyMine',decisions:'emptyDecisions',followup:'emptyFollowup',collaboration:'emptyCollaboration'}[name]),'i9-empty'));
      const cards=el('div',undefined,'i9-cards');
      for(const c of s.items){const r=c.item,card=el('article',undefined,'i9-card');card.dataset.actionId=r.id;
        const day=task?r.approved_date:r.supported_date;
        card.append(el('h3',tr(r.step==='school-session'?'school':r.step==='home-visit'?'visit':'question')),el('p',tr(c.reason),'i9-reason'));
        const meta=el('div',undefined,'i9-meta');meta.append(day===null?el('span',tr('noDate')):el('time',day));
        if(task)meta.append(el('span',tr('assignee')+(locale==='zh-CN'?'：':': ')+(r.assignee==='joint'?tr('joint'):r.assignee==='i2-clara'?'Clara':'Devon')));
        const open=button(tr('details'),()=>inspect(r.id,task?'task':name==='followup'?'followup':'pending'));open.dataset.i9Open=r.id;card.append(meta,open);cards.append(card);
      }section.append(cards);main.append(section);
    }
  }
  root.SamasActionHome=Object.freeze({parse,render,checking,copy});
  if(typeof module!=='undefined')module.exports=root.SamasActionHome;
})(globalThis);
