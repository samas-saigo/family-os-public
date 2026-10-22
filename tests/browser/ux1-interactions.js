'use strict';
// Optional offline browser checks. Local-content injection bypasses CSP; not a
// substitute for the manual Windows file-opening/CSP gate. No server or downloads.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const i=require('../../prototypes/h0-workbench/i18n.js');
const root=path.resolve(__dirname,'../../prototypes/h0-workbench');
let passed=0;
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.H0_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-crashpad-for-testing','--disable-background-networking']});
 try {
  const context=await browser.newContext({offline:true,bypassCSP:true,viewport:{width:1440,height:1000}});
  const requests=[],errors=[];
  await context.route('**/*',r=>{requests.push(r.request().url());r.abort();});
  const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));
  async function load({empty=false,fault=null,long=false,completed=false,longHome=false,capture=false}={}){
   await page.goto('about:blank');
   await page.setContent(fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script[^>]*src[^>]*><\/script>/g,'').replace(/<link[^>]*href[^>]*>/g,''),{waitUntil:'domcontentloaded'});
   await page.addStyleTag({content:fs.readFileSync(path.join(root,'styles.css'),'utf8')});
   for(const file of ['fixtures.js','translations.js','i18n.js','model.js','presentation.js']){await page.addScriptTag({content:fs.readFileSync(path.join(root,file),'utf8')});if(file==='translations.js'&&(long||longHome))await page.evaluate(({longHome})=>{const row=FamilyH1Translations.find(r=>r[0]===(longHome?'fixture.task-school.title':'fixture.workshop.title'));row[1]='A very long household workshop title with multiple choices and follow-up arrangements to inspect carefully';row[2]='学校工作坊的家庭偏好选择与后续安排需要进一步确认的非常长的说明';if(longHome){row[1]+=' with another independently planned synthetic household follow-up and additional arrangements';row[2]+='以及第二项独立的虚构家庭后续安排与额外事项的完整说明';}},{longHome});}
   if(empty||fault||completed||capture)await page.evaluate(({empty,fault,completed,capture})=>{const Base=FamilyH0Model.Workbench;FamilyH0Model.Workbench=class extends Base{constructor(){super();if(empty){this.state.items=[];this.state.tasks=[];this.state.events=[];}if(completed){this.state.tasks.forEach(t=>t.status='completed');globalThis.__testModel=this;}if(capture)globalThis.__testModel=this;}save(...args){return fault?{outcome:fault}:super.save(...args);}};},{empty,fault,completed,capture});
   await page.addScriptTag({content:fs.readFileSync(path.join(root,'app.js'),'utf8')});
  }
  const tr=(locale,key,values)=>i.t(locale,key,values);
  const nav=async(locale,key)=>{const b=page.locator('.sidebar').getByRole('button',{name:new RegExp(tr(locale,key))});if(!(await b.isVisible()))await page.locator('#secondary-menu>summary').click();await b.click();};
  const language=async(value)=>{if(!(await page.locator('#language').isVisible()))await page.locator('#secondary-menu>summary').click();await page.locator('#language').selectOption(value);};
  const dialog=page.getByRole('dialog');
  const card=(locale,id,field='title')=>page.locator('main article').filter({has:page.getByRole('heading',{name:tr(locale,`fixture.${id}.${field}`),exact:true})});
  const inspect=async(locale,id,field)=>card(locale,id,field).getByRole('button').click();
  const click=async(locale,key)=>dialog.getByRole('button',{name:tr(locale,key),exact:true}).click();
  async function fillSearch(value) { if(!(await page.locator('#search').isVisible()))await page.locator('#search-controls>summary').click();await page.locator('#search').fill(value); }
  async function check(name,fn){await fn();passed++;console.log(`PASS ${name}`);}
  async function noEnglish(){
   const text=await page.locator('body').innerText();
   const words=text.match(/[A-Za-z][A-Za-z0-9]*/g)||[];
   const allowed=new Set(['Samas','Family','OS','English','H1','JavaScript','Moss','Mug','Lantern','Trails','Old','Leaf','DEMO15','DEMO','WEEKEND','OLD','verify','mailbox','example','invalid','f']);
   assert.ok(words.every(w=>allowed.has(w)),`Untranslated Chinese UI: ${words.filter(w=>!allowed.has(w)).join(', ')}`);
  }
  await load();
  async function feedbackEmpty() {
   assert.equal(await page.locator('#feedback').textContent(),'');
   assert.equal(await page.locator('#feedback').getAttribute('data-active'),'false');
   assert.equal(await page.locator('#feedback').getAttribute('aria-live'),'polite');
  }
  for(const locale of i.LOCALES) {
   await check(`${locale}: archive feedback clears on archived/active navigation, never becomes a disclaimer`,async()=>{
    await load();await feedbackEmpty();await language(locale);await nav(locale,'ui.pending.confirmation');await feedbackEmpty();
    await inspect(locale,'workshop');await click(locale,'pending.archive');await click(locale,'pending.archive.save');
    assert.equal(await page.locator('#feedback').innerText(),tr(locale,'result.archive'));
    assert.equal(await page.locator('#feedback').getAttribute('data-active'),'true');
    await page.locator('[data-bucket=archived]').click();await feedbackEmpty();assert.equal(await card(locale,'workshop').count(),1);
    await page.locator('[data-bucket=active]').click();await feedbackEmpty();assert.equal(await card(locale,'workshop').count(),0);
   });
   await check(`${locale}: deferral feedback clears on later, search, pagination and ordinary navigation`,async()=>{
    await load();await language(locale);await nav(locale,'ui.pending.confirmation');await inspect(locale,'visit');await click(locale,'ui.defer.question');await click(locale,'ui.confirm.deferral');
    assert.equal(await page.locator('#feedback').innerText(),tr(locale,'result.defer'));
    await page.locator('[data-bucket=later]').click();await feedbackEmpty();assert.equal(await card(locale,'visit').count(),1);
    await page.locator('[data-bucket=active]').click();await page.getByRole('button',{name:tr(locale,'ui.next'),exact:true}).click();await feedbackEmpty();
    await fillSearch('unmatched');await feedbackEmpty();await nav(locale,'ui.home');await feedbackEmpty();
   });
  }
  await check('global language switch replaces feedback after explicit cancellation without saving the unfinished confirmation',async()=>{
   await load();await nav('zh-CN','ui.pending.confirmation');await inspect('zh-CN','visit');await click('zh-CN','ui.defer.question');await click('zh-CN','ui.confirm.deferral');
   await language('en-US');assert.equal(await page.locator('#feedback').innerText(),tr('en-US','locale.ready'));
   await nav('en-US','ui.pending.confirmation');await feedbackEmpty();await inspect('en-US','workshop');await click('en-US','pending.archive');
   await click('en-US','ui.cancel.no.change');await language('zh-CN');
   assert.equal(await page.locator('#feedback').innerText(),tr('zh-CN','locale.ready'));
   await nav('zh-CN','ui.pending.confirmation');await feedbackEmpty();assert.equal(await card('zh-CN','workshop').count(),1);
  });
  await load();
  await check('one responsive global language picker and contextual modal headers cover details, confirmations and settings',async()=>{
   const unique=async width=>{
    assert.equal(await page.locator('select:has(option[value="zh-CN"]):has(option[value="en-US"])').count(),1);
    assert.equal(await page.locator(width<=730?'#secondary-body #language':'.topbar #language').count(),1);
   };
   const contextual=async width=>{await unique(width);assert.deepEqual(await dialog.locator('.dialog-top').evaluate(n=>[...n.children].map(c=>c.tagName)),['SMALL','BUTTON']);assert.equal(await dialog.locator('#language,#member,#reset,#demo-controls').count(),0);};
   for(const width of [1440,390,320])for(const locale of i.LOCALES){
    await page.setViewportSize({width,height:844});await load();await language(locale);await unique(width);
    await nav(locale,'ui.needs.action');await inspect(locale,'task-school');await contextual(width);assert.equal(await dialog.locator('#task-assignee').count(),1);
    await click(locale,'ux.assign');await contextual(width);await page.keyboard.press('Escape');
    await nav(locale,'ui.pending.confirmation');await inspect(locale,'workshop');await contextual(width);await click(locale,'ui.accept.suggested.step');await contextual(width);await click(locale,'ui.cancel.no.change');
    await nav(locale,'ui.security.review');await inspect(locale,'login-risk');await contextual(width);await page.keyboard.press('Escape');
    if(!await page.locator('#demo-controls').isVisible())await page.locator('#secondary-menu>summary').click();await page.locator('#demo-controls').click();await contextual(width);
    await dialog.locator('.source-row').first().getByRole('button').click();await contextual(width);await page.keyboard.press('Escape');
    if(!await page.locator('#reset').isVisible())await page.locator('#secondary-menu>summary').click();await page.locator('#reset').click();await contextual(width);await click(locale,'ui.cancel.keep.demo.state');
   }
  });
  await check('cancel, Escape and Back then the sole global language entry preserve both adults unfinished decisions and keyboard focus',async()=>{
   for(const width of [1440,390,320])for(const who of ['nora','julian'])for(const [op,exit] of [['ui.accept.suggested.step','cancel'],['pending.archive','escape'],['ui.defer.question','back']]){
    const locale=exit==='back'?'en-US':'zh-CN',next=locale==='zh-CN'?'en-US':'zh-CN';
    await page.setViewportSize({width,height:844});await load({capture:true});if(!await page.locator('#member').isVisible())await page.locator('#secondary-menu>summary').click();await page.locator('#member').selectOption(who);await language(locale);await nav(locale,'ui.pending.confirmation');
    const before=await page.evaluate(()=>JSON.stringify(globalThis.__testModel.state));await inspect(locale,'workshop');await click(locale,op);
    if(exit==='cancel')await click(locale,'ui.cancel.no.change');else if(exit==='escape')await page.keyboard.press('Escape');else{await click(locale,'ux.back');assert.equal(await dialog.getAttribute('data-mode'),'detail');await click(locale,'ui.back.to.workbench');}
    assert.equal(await dialog.count(),0);assert.equal(await page.evaluate(()=>document.activeElement.id),'view-heading');
    if(width<=730){await page.locator('#secondary-menu>summary').focus();await page.keyboard.press('Enter');}
    await page.locator('#language').focus();assert.equal(await page.evaluate(()=>document.activeElement.id),'language');await page.locator('#language').selectOption(next);
    assert.equal(await dialog.count(),0);assert.equal(await page.evaluate(()=>JSON.stringify(globalThis.__testModel.state)),before);assert.equal(await card(next,'workshop').count(),1);
    assert.equal(await page.evaluate(()=>document.activeElement===document.querySelector(innerWidth<=730?'#secondary-menu>summary':'#language')),true);
    assert.equal(await page.locator('#feedback').innerText(),tr(next,'locale.ready'));
   }
  });
  await page.setViewportSize({width:1440,height:1000});await load();
  await check('one household app, five primary tabs and clickable authorized totals',async()=>{
   assert.equal(await page.locator('.nav-main button').count(),5);assert.equal(await page.locator('.nav-extra button').count(),2);
   assert.equal(await page.locator('main .coupon').count(),0);
   await page.locator('.stat').filter({hasText:tr('zh-CN','ui.unresolved.questions')}).click();assert.equal(await page.locator('#view-heading').innerText(),tr('zh-CN','ui.pending.confirmation'));
  });
  for(const locale of i.LOCALES){
   await check(`${locale}: assignment select, Cancel and Back never save; independent confirmation does`,async()=>{
    await load();await language(locale);await nav(locale,'ui.needs.action');await inspect(locale,'task-school');
    assert.equal(await page.locator('#task-assignee').inputValue(),'nora');await page.locator('#task-assignee').selectOption('julian');await click(locale,'ux.assign');await click(locale,'ux.back');assert.equal(await page.locator('#task-assignee').inputValue(),'nora');
    await page.locator('#task-assignee').selectOption('julian');await click(locale,'ux.assign');await click(locale,'ui.cancel.no.change');await inspect(locale,'task-school');assert.equal(await page.locator('#task-assignee').inputValue(),'nora');
    await page.locator('#task-assignee').selectOption('julian');await click(locale,'ux.assign');await click(locale,'ux.assign.save');
    await page.locator('#member').selectOption('julian');await language(locale);await nav(locale,'ui.needs.action');await inspect(locale,'task-school');assert.equal(await page.locator('#task-assignee').inputValue(),'julian');await click(locale,'ui.back.to.workbench');
   });
   await check(`${locale}: completion and reopening are shared tracking, not external execution`,async()=>{
    await inspect(locale,'task-school');await click(locale,'ui.simulate.completion');assert.ok((await dialog.innerText()).includes(tr(locale,'ui.this.updates.shared.demo.tracking.only')));await click(locale,'ui.confirm.simulated.tracking.change');
    await page.getByRole('button',{name:tr(locale,'ui.show.simulated.completed.steps')}).click();await inspect(locale,'task-school');await click(locale,'ui.simulate.reopening');await click(locale,'ui.confirm.simulated.tracking.change');assert.equal(await card(locale,'task-school').count(),1);
   });
  }
  await check('settings are ordinary and actual account connection is visibly unsupported',async()=>{
   await load();await page.locator('#demo-controls').click();assert.equal(await dialog.getByRole('button',{name:tr('zh-CN','ux.connect.disabled')}).isDisabled(),true);assert.ok((await dialog.innerText()).includes(tr('zh-CN','ux.settings.note')));await click('zh-CN','ui.close.controls');
  });
  await check('deferred items leave primary but remain in same-page category',async()=>{
   await nav('zh-CN','ui.pending.confirmation');await inspect('zh-CN','visit');await click('zh-CN','ui.defer.question');await click('zh-CN','ui.confirm.deferral');
   assert.equal(await card('zh-CN','visit').count(),0);assert.ok((await page.locator('[data-bucket=active]').innerText()).includes('7'));
   await page.locator('[data-bucket=later]').click();assert.ok((await card('zh-CN','visit').innerText()).includes(tr('zh-CN','ui.deferred.unresolved')));
   assert.equal(await page.getByRole('button',{name:tr('zh-CN','ui.next'),exact:true}).isDisabled(),true);
  });
  await check('unknown safety cannot imply clearance, and suspicious destinations are inert',async()=>{
   await nav('zh-CN','ui.security.review');assert.ok((await page.locator('main').innerText()).includes(tr('zh-CN','safety.UNKNOWN')));await inspect('zh-CN','login-risk');assert.equal(await dialog.getByRole('button',{name:tr('zh-CN','ui.accept.suggested.step')}).count(),0);assert.equal(await dialog.locator('a').count(),0);await click('zh-CN','ui.back.to.workbench');
  });
  await check('promotions require a deliberate query, never enter home/pending/calendar',async()=>{
   for(const key of ['ui.home','ui.pending.confirmation','ui.upcoming']){await nav('zh-CN',key);assert.equal(await page.locator('main .coupon').count(),0);assert.equal(await card('zh-CN','expired-offer').count(),0);}
   await nav('zh-CN','ui.offers');assert.equal(await page.locator('main .coupon').count(),0);await page.getByRole('button',{name:tr('zh-CN','ui.find.fictional.offers')}).click();assert.equal(await page.locator('main .coupon').count(),3);assert.equal(await card('zh-CN','promo-risk').count(),0);
  });
  await check('desktop and both narrow widths fit every destination and dialog in both languages',async()=>{
   await load();for(const locale of i.LOCALES){await language(locale);for(const width of [1440,390,320]){await page.setViewportSize({width,height:900});for(const key of ['ui.home','ui.needs.action','ui.pending.confirmation','ui.upcoming','ui.security.review','ui.quiet.information','ui.offers']){await nav(locale,key);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${locale} ${width} ${key}`);}await nav(locale,'ui.needs.action');await inspect(locale,'task-school');assert.ok(await dialog.evaluate(n=>n.scrollWidth<=n.clientWidth));await page.keyboard.press('Escape');}}
  });
  await check('keyboard can open totals and cancel a decision without acceptance',async()=>{
   await load();await page.locator('.stat').nth(1).focus();await page.keyboard.press('Enter');await inspect('zh-CN','workshop');await click('zh-CN','ui.accept.suggested.step');await page.keyboard.press('Escape');assert.equal(await dialog.count(),0);await nav('zh-CN','ui.needs.action');assert.equal(await card('zh-CN','workshop','step').count(),0);
  });
  await check('mobile home exposes an authorized action above the fixed navigation without scrolling',async()=>{
   for(const width of [390,320])for(const member of ['nora','julian'])for(const locale of i.LOCALES){
    await page.setViewportSize({width,height:844});await load();
    await page.locator('#secondary-menu>summary').click();await page.locator('#member').selectOption(member);await language(locale);
    await nav(locale,'ui.home');await page.evaluate(()=>scrollTo(0,0));
    const heading=await page.locator('main article h3').first().boundingBox();const bottom=await page.locator('.nav-main').boundingBox();
    assert.ok(heading && bottom && heading.y>=0 && heading.y+heading.height<bottom.y,`${width} ${member} ${locale}: actionable heading must precede navigation`);
    assert.equal(await page.evaluate(()=>scrollY),0);
    assert.equal(await page.locator('#secondary-menu').evaluate(n=>n.open),false);
    assert.equal(await page.locator('#search-controls').evaluate(n=>n.open),false);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.equal(await page.locator('main .coupon').count(),0);
    console.log(`VISIBLE ${width}x844 ${member} ${locale}: heading bottom=${Math.round(heading.y+heading.height)}, navigation top=${Math.round(bottom.y)}`);
   }
  });
  await check('compact menus retain keyboard, search and all secondary destinations',async()=>{
   await page.setViewportSize({width:320,height:844});await load();
   const summary=page.locator('#secondary-menu>summary');await summary.focus();await page.keyboard.press('Enter');
   assert.equal(await page.locator('#demo-controls').isVisible(),true);assert.equal(await page.locator('#reset').isVisible(),true);
   assert.equal(await page.locator('#member').isVisible(),true);assert.equal(await page.locator('#language').isVisible(),true);
   await nav('zh-CN','ui.offers');assert.equal(await page.locator('main .coupon').count(),0);
   await nav('zh-CN','ui.home');await page.locator('#search-controls>summary').focus();await page.keyboard.press('Enter');
   assert.equal(await page.locator('#search').isVisible(),true);await fillSearch('出游包');assert.equal(await page.locator('main .task-line').count(),1);await fillSearch('');
   await nav('zh-CN','ui.needs.action');await inspect('zh-CN','task-school');await click('zh-CN','ui.simulate.completion');await page.keyboard.press('Escape');assert.equal(await card('zh-CN','task-school').count(),1);
   for(const node of [summary,page.locator('#search-controls>summary'),...await page.locator('.nav-main button').all()])assert.ok((await node.boundingBox()).height>=44);
   await page.setViewportSize({width:1440,height:1000});await load();
  });
  for(const locale of i.LOCALES) {
   await check(`${locale}: inspect and cancel never archive; confirm removes primary and reopen restores`,async()=>{
    await page.setViewportSize({width:1440,height:1000});await load();await language(locale);await nav(locale,'ui.pending.confirmation');
    await inspect(locale,'workshop');assert.equal(await dialog.getByRole('button',{name:tr(locale,'ui.record.simulated.review.only')}).count(),0);
    await click(locale,'ui.back.to.workbench');assert.equal(await card(locale,'workshop').count(),1);
    await inspect(locale,'workshop');await click(locale,'pending.archive');await click(locale,'ui.cancel.no.change');assert.equal(await card(locale,'workshop').count(),1);
    await inspect(locale,'workshop');await click(locale,'pending.archive');await click(locale,'pending.archive.save');assert.equal(await card(locale,'workshop').count(),0);
    await page.locator('[data-bucket=archived]').click();await inspect(locale,'workshop');assert.equal(await dialog.getByRole('button',{name:tr(locale,'ui.accept.suggested.step')}).count(),0);
    await dialog.locator('.context-details>summary').click();assert.ok((await dialog.innerText()).includes(tr(locale,'history.archive')));await click(locale,'pending.reopen');await click(locale,'ui.cancel.no.change');assert.equal(await card(locale,'workshop').count(),1);
    await inspect(locale,'workshop');await click(locale,'pending.reopen');await click(locale,'pending.reopen.save');assert.equal(await card(locale,'workshop').count(),0);
    await page.locator('[data-bucket=active]').click();assert.equal(await card(locale,'workshop').count(),1);
    await nav(locale,'ui.needs.action');assert.equal(await card(locale,'workshop','step').count(),0);
   });
   await check(`${locale}: archive is personal and revoked sources cannot disclose archived content`,async()=>{
    await nav(locale,'ui.pending.confirmation');await inspect(locale,'workshop');await click(locale,'pending.archive');await click(locale,'pending.archive.save');
    await page.locator('#member').selectOption('julian');await language(locale);await nav(locale,'ui.pending.confirmation');assert.equal(await card(locale,'workshop').count(),1);
    await page.locator('[data-bucket=archived]').click();assert.equal(await card(locale,'workshop').count(),0);
    await page.locator('[data-bucket=active]').click();await inspect(locale,'workshop');assert.ok(!(await dialog.innerText()).includes(tr(locale,'history.archive')));
    await click(locale,'pending.archive');await click(locale,'pending.archive.save');await page.locator('[data-bucket=archived]').click();assert.equal(await card(locale,'workshop').count(),1);
    await page.locator('#member').selectOption('nora');await page.locator('#demo-controls').click();
    await dialog.locator('.source-row').filter({hasText:tr(locale,'fixture.notices.title')}).getByRole('button',{name:tr(locale,'format.revokeButton',{member:tr(locale,'member.julian')}),exact:true}).click();await click(locale,'ui.confirm.demo.sharing.change');
    await page.locator('#member').selectOption('julian');await nav(locale,'ui.pending.confirmation');await page.locator('[data-bucket=archived]').click();assert.equal(await card(locale,'workshop').count(),0);assert.ok((await page.locator('[data-bucket=archived]').innerText()).includes('0'));
   });
  }
  await check('changed archived evidence returns unresolved without old acceptance or safety clearance',async()=>{
   await load();await nav('zh-CN','ui.pending.confirmation');await inspect('zh-CN','workshop');await click('zh-CN','pending.archive');await click('zh-CN','pending.archive.save');
   await page.locator('#demo-controls').click();await click('zh-CN','ui.change.the.workshop.evidence.sample');await click('zh-CN','ui.confirm.sample.evidence.change');
   await nav('zh-CN','ui.pending.confirmation');await inspect('zh-CN','workshop');assert.ok((await dialog.innerText()).includes(tr('zh-CN','safety.UNKNOWN')));assert.equal(await dialog.getByRole('button',{name:tr('zh-CN','pending.reopen')}).count(),0);assert.equal(await dialog.getByRole('button',{name:tr('zh-CN','ui.accept.suggested.step')}).count(),0);await click('zh-CN','ui.back.to.workbench');
   await page.locator('[data-bucket=archived]').click();assert.equal(await card('zh-CN','workshop').count(),0);
  });
  await check('mobile categories and confirmed decisions are operable at both narrow widths',async()=>{
   for(const width of [390,320]){
    await page.setViewportSize({width,height:844});await load();await nav('zh-CN','ui.pending.confirmation');
    await inspect('zh-CN','visit');await click('zh-CN','ui.defer.question');await click('zh-CN','ui.confirm.deferral');
    await page.locator('[data-bucket=later]').click();await inspect('zh-CN','visit');await click('zh-CN','pending.archive');assert.ok(await dialog.evaluate(n=>n.scrollWidth<=n.clientWidth));await click('zh-CN','pending.archive.save');
    await page.locator('[data-bucket=archived]').focus();await page.keyboard.press('Enter');await inspect('zh-CN','visit');await click('zh-CN','pending.reopen');await click('zh-CN','pending.reopen.save');
    await page.locator('[data-bucket=active]').click();assert.equal(await card('zh-CN','visit').count(),1);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    for(const control of await page.locator('.pending-buckets button').all())assert.ok((await control.boundingBox()).height>=44);
   }
  });
  for(const locale of i.LOCALES) await check(`${locale}: detail and security omit obsolete review prompts`,async()=>{
   await page.setViewportSize({width:1440,height:1000});await load();await language(locale);await nav(locale,'ui.pending.confirmation');await inspect(locale,'workshop');
   let text=await dialog.innerText();assert.ok(!/Review:|审核：|未审阅|Unreviewed/.test(text));
   assert.equal(await dialog.getByRole('button',{name:tr(locale,'ui.record.simulated.review.only')}).count(),0);
   await dialog.locator('.context-details>summary').click();text=await dialog.innerText();assert.ok(text.includes(tr(locale,'format.evidence',{generation:i.number(locale,1),decision:tr(locale,'state.pending')})));await click(locale,'ui.back.to.workbench');
   await nav(locale,'ui.security.review');text=await page.locator('main').innerText();assert.ok(!/记录已审阅|review annotation/i.test(text));
   await inspect(locale,'login-risk');text=await dialog.innerText();assert.ok(!/Review:|审核：|未审阅|Unreviewed|记录已审阅|review annotation/i.test(text));
   assert.equal(await dialog.getByRole('button',{name:tr(locale,'ui.accept.suggested.step')}).count(),0);await click(locale,'ui.back.to.workbench');
  });
  await check('pending first title, summary and full details control fit both mobile viewports without scrolling',async()=>{
   for(const width of [390,320])for(const locale of i.LOCALES)for(const who of ['nora','julian']){
    await page.setViewportSize({width,height:844});await load();await page.locator('#secondary-menu>summary').click();await page.locator('#member').selectOption(who);await language(locale);await nav(locale,'ui.pending.confirmation');await page.evaluate(()=>scrollTo(0,0));
    const navTop=(await page.locator('.nav-main').boundingBox()).y;
    for(const control of [page.locator('main article h3').first(),page.locator('main article p').first(),page.locator('main article button').first()]){const box=await control.boundingBox();assert.ok(box.y>=0&&box.y+box.height<navTop,`${width} ${locale}: full action before nav`);}
    assert.equal(await page.evaluate(()=>scrollY),0);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    console.log(`PENDING ${width} ${locale} ${who}: button bottom=${Math.round((await page.locator('main article button').first().boundingBox()).y+(await page.locator('main article button').first().boundingBox()).height)}, nav=${Math.round(navTop)}`);
   }
  });
  for(const locale of i.LOCALES)await check(`${locale}: success feedback names the actual committed decision and new task state`,async()=>{
   await page.setViewportSize({width:1440,height:1000});await load();await language(locale);await nav(locale,'ui.pending.confirmation');
   await inspect(locale,'visit');await click(locale,'ui.defer.question');await click(locale,'ui.confirm.deferral');assert.equal(await page.locator('#feedback').innerText(),tr(locale,'result.defer'));
   await inspect(locale,'workshop');await click(locale,'pending.archive');await click(locale,'pending.archive.save');assert.equal(await page.locator('#feedback').innerText(),tr(locale,'result.archive'));
   await page.locator('[data-bucket=archived]').click();await inspect(locale,'workshop');await click(locale,'pending.reopen');await click(locale,'pending.reopen.save');assert.equal(await page.locator('#feedback').innerText(),tr(locale,'result.reopen'));
   await page.locator('[data-bucket=active]').click();await inspect(locale,'workshop');await click(locale,'ui.accept.suggested.step');await click(locale,'ui.confirm.simulated.task.acceptance');assert.equal(await page.locator('#feedback').innerText(),tr(locale,'ui.confirmed.a.fictional.step.was.separately'));
   await nav(locale,'ui.needs.action');await inspect(locale,'task-school');await page.locator('#task-assignee').selectOption('julian');await click(locale,'ux.assign');await click(locale,'ux.assign.save');assert.equal(await page.locator('#feedback').innerText(),tr(locale,'result.assignment',{owner:tr(locale,'member.julian')}));
   await inspect(locale,'task-school');await click(locale,'ui.simulate.completion');await click(locale,'ui.confirm.simulated.tracking.change');assert.equal(await page.locator('#feedback').innerText(),tr(locale,'result.completed'));
   await page.getByRole('button',{name:tr(locale,'ui.show.simulated.completed.steps')}).click();await inspect(locale,'task-school');await click(locale,'ui.simulate.reopening');await click(locale,'ui.confirm.simulated.tracking.change');assert.equal(await page.locator('#feedback').innerText(),tr(locale,'result.taskReopened'));
   await page.locator('#demo-controls').click();await dialog.locator('.source-row').filter({hasText:tr(locale,'fixture.notices.title')}).getByRole('button',{name:tr(locale,'format.revokeButton',{member:tr(locale,'member.julian')}),exact:true}).click();await click(locale,'ui.confirm.demo.sharing.change');assert.equal(await page.locator('#feedback').innerText(),tr(locale,'result.revoked',{member:tr(locale,'member.julian')}));
   await page.locator('#demo-controls').click();await dialog.locator('.source-row').filter({hasText:tr(locale,'fixture.notices.title')}).getByRole('button',{name:tr(locale,'format.allowButton',{member:tr(locale,'member.julian')}),exact:true}).click();await click(locale,'ui.confirm.demo.sharing.change');assert.equal(await page.locator('#feedback').innerText(),tr(locale,'result.allowed',{member:tr(locale,'member.julian')}));
  });
  await check('failed, cancelled and replay outcomes never announce a new successful change',async()=>{
   await page.setViewportSize({width:1440,height:1000});
   for(const fault of ['STALE','DENIED','REPLAY']){
    await load({fault});await nav('zh-CN','ui.pending.confirmation');await inspect('zh-CN','workshop');await click('zh-CN','pending.archive');await click('zh-CN','pending.archive.save');
    const expected={STALE:'ui.not.saved.evidence.or.permissions.changed',DENIED:'ui.not.saved.this.decision.is.unavailable',REPLAY:'ui.already.recorded.no.duplicate.simulated.change'};
    assert.equal(await page.locator('#feedback').innerText(),tr('zh-CN',expected[fault]));assert.equal(await card('zh-CN','workshop').count(),1);
   }
   await load();await nav('zh-CN','ui.pending.confirmation');await inspect('zh-CN','workshop');await click('zh-CN','pending.archive');await click('zh-CN','ui.cancel.no.change');assert.equal(await page.locator('#feedback').innerText(),tr('zh-CN','ui.canceled.no.simulated.decision.was.saved'));
  });
  for(const locale of i.LOCALES)await check(`${locale}: genuine empty categories differ from filtered misses`,async()=>{
   await page.setViewportSize({width:1440,height:1000});await load({empty:true});await language(locale);
   await nav(locale,'ui.pending.confirmation');for(const bucket of ['active','later','archived']){await page.locator(`[data-bucket=${bucket}]`).click();assert.equal(await page.locator('main .empty').innerText(),tr(locale,`empty.${bucket}`));}
   await nav(locale,'ui.needs.action');assert.equal(await page.locator('main .empty').innerText(),tr(locale,'empty.allTasks'));await page.getByRole('button',{name:tr(locale,'ui.show.simulated.completed.steps')}).click();assert.equal(await page.locator('main .empty').innerText(),tr(locale,'empty.allTasks'));
   await load({completed:true});await language(locale);await nav(locale,'ui.needs.action');assert.equal(await page.locator('main .empty').innerText(),tr(locale,'empty.tasks'));
   await load();await language(locale);await nav(locale,'ui.pending.confirmation');await fillSearch('zzzzzz');assert.equal(await page.locator('main .empty').innerText(),tr(locale,'empty.filtered'));assert.equal(await page.locator('main article').count(),0);
   await fillSearch('');assert.equal(await page.locator('main .empty').count(),0);
  });
  await check('compact summaries use two distinct lines and tools do not precede household content by default',async()=>{
   for(const width of [1440,390,320])for(const locale of i.LOCALES){
    await page.setViewportSize({width,height:844});await load();await language(locale);await nav(locale,'ui.home');
    assert.equal(await page.locator('#search-controls').evaluate(n=>n.open),false);
    assert.equal(await page.locator('.stat').count(),4);
    for(const stat of await page.locator('.stat').all()){
     assert.match(await stat.locator('strong').innerText(),/^[0-9]+$/);
     const label=stat.locator('span');assert.ok(!(await label.innerText()).startsWith('项'));
     const n=await stat.locator('strong').boundingBox(),l=await label.boundingBox();assert.ok(l.y>=n.y+n.height);
     assert.ok(parseFloat(await stat.locator('strong').evaluate(n=>getComputedStyle(n).fontSize))<=26);
    }
    const tasks=page.locator('main .section-head h2').first();assert.equal(await tasks.innerText(),tr(locale,'ui.the.next.small.steps'));
    const title=await page.locator('main article h3').first().boundingBox();assert.ok(title.y+title.height< (width<=730?(await page.locator('.nav-main').boundingBox()).y:844));
   }
  });
  await check('one compact filter disclosure keeps search and both filters accessible without duplicate copy',async()=>{
   for(const width of [1440,390,320])for(const locale of i.LOCALES){
    await page.setViewportSize({width,height:844});await load();await language(locale);
    const summary=page.locator('#search-controls>summary');assert.equal(await summary.innerText(),tr(locale,'ux.search'));assert.equal(await page.locator('#search-controls').evaluate(n=>n.open),false);
    await summary.focus();await page.keyboard.press('Enter');
    const search=page.getByRole('searchbox',{name:tr(locale,'chrome.search'),exact:true});assert.ok(await search.isVisible());assert.equal(await page.locator('label[for="search"]').count(),0);
    for(const id of ['category','assignee'])assert.ok(await page.locator('#'+id).isVisible());
    await search.fill('zz-no-match');assert.equal(await page.locator('main article').count(),0);await search.fill('');
    await page.locator('#assignee').selectOption('me');assert.ok((await page.locator('#assignee').inputValue())==='me');await page.locator('#assignee').selectOption('all');
    const options=await page.locator('#category option').evaluateAll(ns=>ns.map(n=>n.value));assert.ok(options.length>1);await page.locator('#category').selectOption(options[1]);assert.equal(await page.locator('#category').inputValue(),options[1]);await page.locator('#category').selectOption('all');
    await summary.click();assert.equal(await search.isVisible(),false);
   }
  });
  await check('home regions use the shared spacing rhythm with compact rows and reachable mobile actions',async()=>{
   for(const width of [1440,390,320])for(const locale of i.LOCALES){
    await page.setViewportSize({width,height:844});await load();await language(locale);await nav(locale,'ui.home');
    for(const expanded of [false,true]){
     if(expanded)await page.locator('#search-controls>summary').click();
     const gap=await page.evaluate(()=>{const box=s=>document.querySelector(s).getBoundingClientRect();const tools=box('#search-controls'),hero=box('main .hero'),stats=box('.stats'),columns=box('.columns'),head=box('.columns .section-head'),row=box('.columns .task-line'),later=box('.columns .section-spaced'),last=[...document.querySelectorAll('.columns .task-line')].at(-1).getBoundingClientRect();return {tools:hero.top-tools.bottom,title:stats.top-hero.bottom,overview:columns.top-stats.bottom,heading:row.top-head.bottom,section:later.top-last.bottom};});
     for(const [key,expected] of Object.entries({tools:24,title:width<=730?20:24,overview:width<=730?28:32,heading:16,section:width<=730?32:36}))assert.ok(Math.abs(gap[key]-expected)<=1,`${width} ${locale} ${key}: ${gap[key]}`);
     assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    await page.locator('#search-controls>summary').click();await page.evaluate(()=>scrollTo(0,0));
    if(width<=730){const h=await page.locator('main article h3').first().boundingBox(),action=await page.locator('main article button').first().boundingBox(),bottom=await page.locator('.nav-main').boundingBox();assert.ok(h.y+h.height<bottom.y);assert.ok(action.y+action.height<bottom.y);}
   }
  });
  await check('overview cards fill the dashboard uniformly and route by the current authorized counts',async()=>{
   const destinations=['ui.needs.action','ui.pending.confirmation','ui.upcoming','ui.security.review'];
   for(const width of [1440,390,320])for(const who of ['nora','julian'])for(const locale of i.LOCALES){
    await page.setViewportSize({width,height:844});await load();
    if(!(await page.locator('#member').isVisible()))await page.locator('#secondary-menu>summary').click();await page.locator('#member').selectOption(who);await language(locale);await nav(locale,'ui.home');await page.mouse.move(0,0);
    const expected=await page.evaluate(({who,locale})=>{const p=FamilyH1Presentation.project(new FamilyH0Model.Workbench(),who,locale,{view:'home'});return [p.counts.tasks,p.counts.pending,p.counts.upcoming,p.counts.security];},{who,locale});
    const boxes=await page.locator('.stat').evaluateAll(ns=>ns.map(n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return {x:r.x,y:r.y,w:r.width,h:r.height,bg:s.backgroundColor,border:s.borderTopColor,align:s.textAlign};}));
    assert.equal(new Set(boxes.map(b=>b.bg)).size,1);assert.equal(new Set(boxes.map(b=>b.border)).size,1);
    for(const b of boxes){assert.ok(Math.abs(b.w-boxes[0].w)<=1);assert.ok(Math.abs(b.h-boxes[0].h)<=1);assert.equal(b.align,'center');assert.equal(b.y,boxes[0].y);assert.notEqual(b.bg,'rgba(0, 0, 0, 0)');}
    const mainBox=await page.locator('main').boundingBox();assert.ok(Math.abs(boxes[0].x-mainBox.x)<=1);assert.ok(Math.abs(boxes[3].x+boxes[3].w-mainBox.x-mainBox.width)<=1);
    for(let n=0;n<4;n++){
     const control=page.locator('.stat').nth(n);assert.equal(await control.locator('strong').innerText(),i.number(locale,expected[n]));assert.equal(await control.getAttribute('aria-pressed'),null);
     await control.click({position:{x:6,y:6}});assert.equal(await page.locator('#view-heading').innerText(),tr(locale,destinations[n]));await nav(locale,'ui.home');
    }
   }
  });
  await check('desktop household task and date rows are compact without fixed-height clipping',async()=>{
   for(const who of ['nora','julian'])for(const locale of i.LOCALES){
    await page.setViewportSize({width:1440,height:1000});await load();await page.locator('#member').selectOption(who);await language(locale);await nav(locale,'ui.home');
    for(const row of await page.locator('.columns .task-line').all()){
     const box=await row.boundingBox(),heading=await row.locator('h3').boundingBox(),action=await row.locator('button').boundingBox();
     assert.ok(box.height>=80);if(heading.height<=26)assert.ok(box.height<=100,`task height ${box.height}`);assert.ok(action.y>=box.y&&action.y+action.height<=box.y+box.height);
     assert.ok(await row.evaluate(n=>n.scrollHeight<=n.clientHeight+1));
    }
    for(const row of await page.locator('.columns .event').all()){const box=await row.boundingBox(),heading=await row.locator('h3').boundingBox();assert.ok(box.height>=80);if(heading.height<=24)assert.ok(box.height<=100,`date height ${box.height}`);assert.ok(await row.evaluate(n=>n.scrollHeight<=n.clientHeight+1));}
   }
  });
  await check('long home task titles expand naturally with readable actions at narrow and zoom-equivalent widths',async()=>{
   for(const width of [1440,720,390,320])for(const locale of i.LOCALES){
    await page.setViewportSize({width,height:844});await load({longHome:true});await language(locale);await nav(locale,'ui.home');
    const row=page.locator('.columns .task-line').first(),heading=row.locator('h3'),action=row.locator('button');
    const box=await row.boundingBox(),h=await heading.boundingBox(),b=await action.boundingBox();assert.ok(h.height>25);assert.ok(box.height>=h.height+24);assert.ok(b.y>=box.y&&b.y+b.height<=box.y+box.height);
    assert.ok(await row.evaluate(n=>n.scrollHeight<=n.clientHeight+1&&n.scrollWidth<=n.clientWidth+1));assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.equal(await heading.evaluate(n=>getComputedStyle(n).textOverflow),'clip');assert.ok(parseFloat(await heading.evaluate(n=>getComputedStyle(n).fontSize))>=17);
    await action.scrollIntoViewIfNeeded();const visible=await action.boundingBox();assert.ok(visible.y>=0);if(width<=730)assert.ok(visible.y+visible.height<(await page.locator('.nav-main').boundingBox()).y);
   }
  });
  await check('buttons expose distinct neutral, primary, hover, pressed and keyboard-focus states',async()=>{
   for(const locale of i.LOCALES){
    await page.setViewportSize({width:1440,height:1000});await load();await language(locale);await nav(locale,'ui.home');
    const details=page.locator('main article button').first();
    const style=n=>{const s=getComputedStyle(n);return {background:s.backgroundColor,border:s.borderTopColor,width:s.borderTopWidth,height:n.getBoundingClientRect().height};};
    const resting=await details.evaluate(style);assert.equal(resting.width,'1px');assert.ok(resting.height>=44);assert.notEqual(resting.border,'rgb(226, 229, 233)');
    const luminance=value=>{const rgb=value.match(/[0-9.]+/g).slice(0,3).map(v=>Number(v)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return rgb.reduce((sum,v,n)=>sum+v*[.2126,.7152,.0722][n],0);};
    const tones=[luminance(resting.border),luminance(resting.background)].sort((a,b)=>a-b);assert.ok((tones[1]+.05)/(tones[0]+.05)>=3,'secondary button boundary contrast');
    await details.hover();await page.waitForTimeout(200);const hover=await details.evaluate(style);assert.notDeepEqual(hover,resting);
    await page.mouse.down();await page.waitForTimeout(200);const pressed=await details.evaluate(style);assert.notEqual(pressed.background,hover.background);await page.mouse.up();await click(locale,'ui.back.to.workbench');
    await nav(locale,'ui.pending.confirmation');await inspect(locale,'workshop');await click(locale,'ui.accept.suggested.step');
    const primary=dialog.getByRole('button',{name:tr(locale,'ui.confirm.simulated.task.acceptance'),exact:true}),cancel=dialog.getByRole('button',{name:tr(locale,'ui.cancel.no.change'),exact:true});
    assert.notEqual((await primary.evaluate(style)).background,(await cancel.evaluate(style)).background);
    await page.keyboard.press('Tab');await cancel.focus();await page.keyboard.press('Tab');await page.keyboard.press('Shift+Tab');
    assert.ok(await cancel.evaluate(n=>n.matches(':focus-visible')));assert.ok(parseFloat(await cancel.evaluate(n=>getComputedStyle(n).outlineWidth))>=3);await page.keyboard.press('Escape');
   }
  });
  await check('the typographic Samas wordmark stays accessible without graphic icons across navigation',async()=>{
   for(const width of [1440,390,320])for(const locale of i.LOCALES){
    await page.setViewportSize({width,height:844});await load();await language(locale);
    const brand=page.getByRole('img',{name:'Samas Family OS',exact:true});assert.equal(await brand.locator('.brand-word').innerText(),'Samas');
    assert.equal(await brand.locator('svg,img,.brand-symbol,.brand-mark').count(),0);assert.equal(await brand.locator('.brand-word').evaluate(n=>getComputedStyle(n).fontWeight),'400');
    const b=await brand.boundingBox();assert.ok(b.x>=0&&b.x+b.width<=width);assert.ok(await brand.evaluate(n=>n.scrollWidth<=n.clientWidth));
    if(width<=730){const menu=await page.locator('#secondary-menu>summary').boundingBox();assert.ok(b.x+b.width<=menu.x);}
   }
  });
  await check('completed-task toggle is fully readable and reveals or hides completed tasks without mutation',async()=>{
   for(const width of [1440,1152,960,720,390,320])for(const locale of i.LOCALES){
    await page.setViewportSize({width,height:width===720?500:844});await load({completed:true});await language(locale);await nav(locale,'ui.needs.action');
    const history=await page.evaluate(()=>JSON.stringify(globalThis.__testModel.state));
    for(const key of ['ui.show.simulated.completed.steps','ui.hide.simulated.completed.steps']){
     const toggle=page.getByRole('button',{name:tr(locale,key),exact:true});await toggle.scrollIntoViewIfNeeded();
     const fit=await toggle.evaluate(n=>{const b=n.getBoundingClientRect(),r=document.createRange();r.selectNodeContents(n);return {box:{x:b.x,y:b.y,right:b.right,bottom:b.bottom,height:b.height},text:[...r.getClientRects()].map(t=>({left:t.left,right:t.right,top:t.top,bottom:t.bottom})),decoration:getComputedStyle(n).textDecorationLine,overflow:n.scrollWidth>n.clientWidth||n.scrollHeight>n.clientHeight};});
     assert.equal(fit.overflow,false);assert.equal(fit.decoration,'none');assert.ok(fit.box.height>=44);assert.ok(fit.box.x>=0&&fit.box.right<=width);
     for(const t of fit.text){assert.ok(t.left>=fit.box.x&&t.right<=fit.box.right);assert.ok(t.top>=fit.box.y&&t.bottom<=fit.box.bottom);}
     await toggle.click();assert.equal(await card(locale,'task-school').count(),key==='ui.show.simulated.completed.steps'?1:0);
    }
    assert.equal(await page.evaluate(()=>JSON.stringify(globalThis.__testModel.state)),history);
   }
  });
  await check('assignment, task actions and confirmation labels remain complete without literal ellipses',async()=>{
   const complete=async()=>{const problems=await page.locator('button').evaluateAll(ns=>ns.filter(n=>n.getClientRects().length).filter(n=>/(?:\.\.\.|…)[\s]*$/.test(n.textContent.trim())||getComputedStyle(n).textOverflow==='ellipsis'||n.scrollWidth>n.clientWidth+1||n.scrollHeight>n.clientHeight+1).map(n=>n.textContent.trim()));assert.deepEqual(problems,[]);};
   for(const width of [1440,1152,960,720,390,320])for(const locale of i.LOCALES){
    await page.setViewportSize({width,height:width===720?500:844});await load();await language(locale);
    for(const key of ['ui.home','ui.needs.action','ui.pending.confirmation','ui.upcoming','ui.security.review','ui.quiet.information']){await nav(locale,key);await complete();}
    await nav(locale,'ui.needs.action');await inspect(locale,'task-school');await complete();await click(locale,'ux.assign');await complete();await click(locale,'ui.cancel.no.change');
    await inspect(locale,'task-school');await click(locale,'ui.simulate.completion');await complete();
    for(const key of ['ui.confirm.simulated.tracking.change','ui.cancel.no.change']){const b=await dialog.getByRole('button',{name:tr(locale,key),exact:true}).boundingBox();assert.ok(b.y>=0&&b.y+b.height<=(await page.viewportSize()).height);}
    await page.keyboard.press('Escape');const settings=page.locator('#demo-controls');if(!(await settings.isVisible()))await page.locator('#secondary-menu>summary').click();await settings.click();await complete();await page.keyboard.press('Escape');
   }
  });
  await check('all visible controls display complete text and remain reachable in both languages and zoom-equivalent reflow',async()=>{
   const fit=async()=>{
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    const issues=await page.locator('button,summary,select').evaluateAll(nodes=>nodes.filter(n=>n.getClientRects().length&&getComputedStyle(n).visibility!=='hidden').flatMap(n=>{
     const box=n.getBoundingClientRect(),style=getComputedStyle(n);let bad=n.scrollWidth>n.clientWidth+1||n.scrollHeight>n.clientHeight+1||style.textOverflow==='ellipsis'||box.height<44;
     if(n.tagName==='SELECT'){const c=document.createElement('canvas').getContext('2d');c.font=style.font;const text=n.selectedOptions[0]?.textContent||'';if(c.measureText(text).width>n.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight)-22)bad=true;}
     if(n.tagName!=='SELECT'){const walker=document.createTreeWalker(n,NodeFilter.SHOW_TEXT);while(walker.nextNode()){if(!walker.currentNode.textContent.trim())continue;const range=document.createRange();range.selectNodeContents(walker.currentNode);for(const r of range.getClientRects())if(r.left<box.left-1||r.right>box.right+1)bad=true;}}
     return bad?[n.textContent.trim()]:[];
    }));assert.deepEqual(issues,[]);
   };
   for(const width of [1440,1152,960,720,390,320])for(const locale of i.LOCALES){
    await page.setViewportSize({width,height:width===720?500:844});await load();await language(locale);
    for(const key of ['ui.home','ui.needs.action','ui.pending.confirmation','ui.upcoming','ui.security.review','ui.offers']){await nav(locale,key);await fit();}
    await nav(locale,'ui.pending.confirmation');await inspect(locale,'workshop');await click(locale,'ui.accept.suggested.step');await fit();
    for(const key of ['ui.confirm.simulated.task.acceptance','ui.cancel.no.change']){const b=dialog.getByRole('button',{name:tr(locale,key),exact:true});const box=await b.boundingBox();assert.ok(box.y>=0&&box.y+box.height<= (await page.viewportSize()).height);}
    await page.keyboard.press('Escape');const settings=page.locator('#demo-controls');if(!(await settings.isVisible()))await page.locator('#secondary-menu>summary').click();await settings.click();await fit();await page.keyboard.press('Escape');
   }
  });
  await check('long titles wrap without truncation and confirmation keeps the save/cancel controls available',async()=>{
   await page.setViewportSize({width:320,height:844});await load({long:true});await nav('zh-CN','ui.pending.confirmation');await page.locator('main article button').first().click();await click('zh-CN','pending.archive');
   assert.ok(await dialog.evaluate(n=>n.scrollWidth<=n.clientWidth));assert.ok((await dialog.locator('.confirmation-target').innerText()).length>25);
   for(const key of ['pending.archive.save','ui.cancel.no.change']){const b=dialog.getByRole('button',{name:tr('zh-CN',key),exact:true});const box=await b.boundingBox();assert.ok(box.y>=0&&box.y+box.height<=844);}
   await page.keyboard.press('Escape');assert.ok((await page.locator('main article h3').first().innerText()).length>25);
  });
  const capture=process.env.UX1_SCREENSHOT_DIR;
  if(capture){
   fs.mkdirSync(capture,{recursive:true});
   for(const [label,width,height] of [['desktop',1440,1000],['mobile',390,844],['narrow',320,844]]){
    await page.setViewportSize({width,height});await load();await nav('zh-CN','ui.pending.confirmation');
    await inspect('zh-CN','visit');await click('zh-CN','ui.defer.question');await click('zh-CN','ui.confirm.deferral');
    await inspect('zh-CN','workshop');await click('zh-CN','pending.archive');await click('zh-CN','pending.archive.save');
    await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(capture,`pending-${label}.png`)});
    if(label==='mobile')for(const bucket of ['later','archived']){await page.locator(`[data-bucket=${bucket}]`).click();await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(capture,`pending-${bucket}.png`)});}
   }
  }
  await check('no network, executable links, persistence or runtime errors',async()=>{assert.deepEqual(requests,[]);assert.deepEqual(errors,[]);assert.deepEqual(await page.locator('a').evaluateAll(ns=>ns.map(n=>n.getAttribute('href'))),['#main']);});
  console.log(`${passed} UX1 browser checks passed; offline injection, Windows opening still a human gate.`);
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
