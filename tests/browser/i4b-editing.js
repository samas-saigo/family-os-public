'use strict';
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {spawn}=require('node:child_process'),{chromium}=require('playwright');
if(!process.argv.includes('--synthetic-only'))throw Error('Exact synthetic opt-in required');
const root=path.resolve(__dirname,'../..'),pause=ms=>new Promise(r=>setTimeout(r,ms));
const child=spawn(process.env.I4B_TEST_PYTHON||path.join(root,'.venv/bin/python'),['-u','tests/browser/i4b-fixture-host.py','--synthetic-only'],{cwd:root,stdio:['pipe','pipe','pipe']});
let output='',browser,count=0,stage='startup';console.log('I4b stage: '+stage);child.stdout.on('data',b=>output+=b);child.stderr.on('data',()=>{});
async function wait(fn){for(let i=0;i<300;i++){if(await fn())return;await pause(100);}throw Error('Synthetic expectation timed out');}
async function command(text){const before=output.split('OK').length;child.stdin.write(text+'\n');await wait(()=>output.split('OK').length>before);}
(async()=>{
  await wait(()=>/Open http:\/\/127\.0\.0\.1:\d+\//.test(output));const origin=output.match(/Open (http:\/\/127\.0\.0\.1:\d+)\//)[1];
  browser=await chromium.launch({executablePath:process.env.I4B_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const ca=await browser.newContext({viewport:{width:1440,height:1000}}),cb=await browser.newContext({viewport:{width:390,height:844}});
  const a=await ca.newPage(),b=await cb.newPage(),errors=[];for(const p of [a,b]){p.setDefaultTimeout(12000);p.on('pageerror',()=>errors.push('browser-error'));}
  const capture=process.argv.includes('--screenshots'),images=path.join(root,'docs/screenshots/i4b');if(capture)fs.mkdirSync(images,{recursive:true});
  const shot=async(p,name)=>{if(capture)await p.screenshot({path:path.join(images,name+'.png'),fullPage:true});};
  const nav=(p,key)=>p.locator('#navigation button[data-view="'+key+'"]').click();
  const modal=p=>p.getByRole('dialog');
  const confirm=p=>modal(p).getByRole('button',{name:'确认修改',exact:true});
  async function login(p,peer){await p.goto(origin);await p.getByRole('button',{name:'发起请求',exact:true}).click();await p.locator('.connection-panel code').waitFor();
    await command('approve '+await p.locator('.connection-panel code').textContent()+' '+peer);await p.locator('.stat').first().waitFor();}
  async function cards(p,n){await wait(async()=>await p.locator('article').count()===n);}
  async function open(p){await p.locator('article').filter({hasText:'2035-06-12'}).getByRole('button',{name:/^(详情|Details)$/}).click();await p.locator('#edit-assignee').waitFor();}
  async function selected(p,value){
    assert.equal(await p.locator('#edit-assignee').inputValue(),value);
    const text=await p.locator('#edit-assignee option:checked').textContent();
    assert(value==='joint'?['共同负责','Jointly managed'].includes(text):text===(value==='i2-clara'?'Clara':'Devon'));
    assert(await modal(p).getByRole('button',{name:/^(调整分工|Change assignment)$/}).isDisabled());
  }
  async function language(p,value){
    const menu=p.locator('#secondary-menu');
    await wait(()=>p.locator('#language-label').evaluate(n=>Boolean(n.closest(matchMedia('(max-width:730px)').matches?'#secondary-body':'.preferences'))));
    if(!await p.locator('#language').isVisible())await menu.locator('summary').click();
    await p.locator('#language').selectOption(value);
    if(await menu.getAttribute('open')!==null)await menu.locator('summary').click();
  }
  async function editLayout(p){
    const layout=await modal(p).evaluate(d=>{
      const select=d.querySelector('#edit-assignee').getBoundingClientRect();
      const actions=d.querySelector('.task-edit-actions'),buttons=[...actions.querySelectorAll('button')];
      const boxes=buttons.map(n=>n.getBoundingClientRect());
      return {separate:actions.getBoundingClientRect().top>=select.bottom+12,
        gap:parseFloat(getComputedStyle(actions).gap),
        fits:buttons.every(n=>n.scrollWidth<=n.clientWidth+1)&&boxes.every(r=>r.left>=0&&r.right<=innerWidth&&r.height>=44),
        noOverlap:boxes.every((a,i)=>boxes.every((b,j)=>i===j||a.right<=b.left||b.right<=a.left||a.bottom<=b.top||b.bottom<=a.top)),
        overflow:d.scrollWidth>d.clientWidth+1};
    });
    assert(layout.separate);assert(layout.gap>=12);assert(layout.fits);assert(layout.noOverlap);assert(!layout.overflow);
  }
  await login(a,'clara');await login(b,'devon');await nav(a,'tasks');await nav(b,'tasks');await cards(a,3);await cards(b,2);count++;
  stage='date-survives-options';console.log('I4b stage: '+stage);
  let releaseOptions;const optionsGate=new Promise(resolve=>{releaseOptions=resolve;});
  await a.route('**/api/tasks/edit-options',async route=>{await optionsGate;await route.continue();});
  try{
    await a.locator('article').filter({hasText:'2035-06-12'}).getByRole('button',{name:'详情',exact:true}).click();
    await modal(a).getByText('2035-06-12',{exact:true}).waitFor();
    assert(await modal(a).getByText('2035-06-12',{exact:true}).isVisible());
  }finally{releaseOptions();}
  await a.locator('#edit-assignee').waitFor();
  assert(await modal(a).getByText('2035-06-12',{exact:true}).isVisible());
  await editLayout(a);assert.match(await modal(a).locator('.task-current-assignee').textContent(),/^负责人：/);count++;
  await selected(a,'joint');
  await a.locator('#edit-assignee').selectOption('i2-clara');
  assert(await modal(a).getByRole('button',{name:'调整分工',exact:true}).isEnabled());
  await a.locator('#edit-assignee').selectOption('joint');await selected(a,'joint');count++;
  await a.unroute('**/api/tasks/edit-options');await a.keyboard.press('Escape');count++;
  await a.locator('article').filter({hasText:'Clara'}).getByRole('button',{name:'详情',exact:true}).click();
  await a.locator('#edit-assignee').waitFor();assert(await modal(a).getByText('未设置日期',{exact:true}).isVisible());
  await selected(a,'i2-clara');count++;
  await a.keyboard.press('Escape');count++;
  stage='default-assignee-views';console.log('I4b stage: '+stage);
  // Use a separate normally paired session so the visual matrix respects the draft cap.
  const cc=await browser.newContext({viewport:{width:1440,height:844}}),c=await cc.newPage();
  c.setDefaultTimeout(12000);c.on('pageerror',()=>errors.push('browser-error'));await login(c,'clara');await nav(c,'tasks');await cards(c,3);
  for(const locale of ['zh-CN','en-US'])for(const width of [1440,390,320]){
    stage='default-assignee-'+locale+'-'+width;
    await c.setViewportSize({width,height:844});await language(c,locale);await open(c);
    await selected(c,'joint');await editLayout(c);await c.keyboard.press('Escape');count++;
    await c.locator('article').filter({hasText:'Clara'}).getByRole('button',{name:/^(详情|Details)$/}).click();
    await c.locator('#edit-assignee').waitFor();await selected(c,'i2-clara');await editLayout(c);await c.keyboard.press('Escape');count++;
  }
  await cc.close();
  // Mock only the reduced options envelope; no writable draft or grant is created.
  const canonical=v=>Array.isArray(v)?'['+v.map(canonical).join(',')+']':v&&typeof v==='object'?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}':JSON.stringify(v);
  stage='restricted-current-value';await a.route('**/api/tasks/edit-options',async route=>{
    const v={schema:'i4b-edit-options-v1',synthetic_only:true,draft:'f'.repeat(32),
      task:{id:route.request().postDataJSON().id,step:'school-session',assignee:'joint',status:'pending',approved_date:'2035-06-12',revision:1,can_edit:true},assignees:['i2-clara']};
    await route.fulfill({status:200,contentType:'application/json',body:canonical(v)});
  });
  await open(a);await selected(a,'joint');
  assert(await a.locator('#edit-assignee option[value="joint"]').isDisabled());
  assert.deepEqual(await a.locator('#edit-assignee option:not(:disabled)').evaluateAll(ns=>ns.map(n=>n.value)),['i2-clara']);
  await a.locator('#edit-assignee').selectOption('i2-clara');assert(await modal(a).getByRole('button',{name:'调整分工',exact:true}).isEnabled());
  await a.keyboard.press('Escape');await a.unroute('**/api/tasks/edit-options');count++;
  let writes=0;a.on('request',r=>{if(new URL(r.url()).pathname==='/api/tasks/edit-confirm')writes++;});
  stage='selection-focus';console.log('I4b stage: '+stage);await open(a);await a.locator('#edit-assignee').selectOption('i2-devon');await a.locator('#edit-assignee').focus();
  const field=await a.locator('#edit-assignee').elementHandle();let polls=0;const observe=r=>{if(new URL(r.url()).pathname==='/api/tasks'&&r.status()===200)polls++;};a.on('response',observe);const started=Date.now();
  await wait(async()=>{assert(await field.evaluate(n=>n.isConnected&&document.activeElement===n&&n.value==='i2-devon'));assert(await modal(a).getByText('2035-06-12',{exact:true}).isVisible());return polls>=2&&Date.now()-started>=10100;});
  a.off('response',observe);await field.dispose();assert.equal(writes,0);count++;
  await modal(a).getByRole('button',{name:'调整分工',exact:true}).click();await confirm(a).waitFor();await shot(a,'assignment-preview-desktop');
  await modal(a).getByRole('button',{name:'取消',exact:true}).click();assert.equal(writes,0);count++;
  stage='assignment';console.log('I4b stage: '+stage);await open(a);await selected(a,'joint');count++;
  await a.locator('#edit-assignee').selectOption('i2-devon');await modal(a).getByRole('button',{name:'调整分工',exact:true}).click();
  await confirm(a).click();await a.getByText('家庭待办已更新',{exact:true}).waitFor();await cards(a,3);assert.equal(writes,1);count++;
  await shot(a,'tasks-clara-desktop');await a.emulateMedia({colorScheme:'dark'});await wait(async()=>await a.locator('html').getAttribute('data-theme')==='dark');await shot(a,'tasks-clara-dark-desktop');await a.emulateMedia({colorScheme:'light'});
  await b.locator('#reload').click();await cards(b,2);await shot(b,'tasks-devon-light-390');
  // Shared school has a date; task identity stays unchanged through completion/reopen.
  const school=p=>p.locator('article').filter({hasText:'2035-06-12'});
  assert((await school(a).textContent()).includes('Devon'));assert((await school(b).textContent()).includes('Devon'));count++;
  async function schoolOpen(p){await school(p).getByRole('button',{name:/^(详情|Details)$/}).click();await p.locator('#edit-assignee').waitFor();assert(await modal(p).getByText('2035-06-12',{exact:true}).isVisible());}
  await schoolOpen(a);assert(await modal(a).getByText('负责人：Devon',{exact:true}).isVisible());
  await selected(a,'i2-devon');await a.locator('#edit-assignee').selectOption('joint');
  assert(await modal(a).getByRole('button',{name:'调整分工',exact:true}).isEnabled());
  await a.locator('#edit-assignee').selectOption('i2-devon');await selected(a,'i2-devon');count++;
  assert(await modal(a).getByText('负责人表示当前主负责成员，不改变这项待办的共享范围。',{exact:true}).isVisible());
  await a.keyboard.press('Escape');await cards(a,3);count++;
  const operation= a.locator('.edit-operation-status');
  assert(await operation.getByText('操作核对',{exact:true}).isVisible());assert.equal(await operation.locator('article').count(),0);
  assert.equal(await operation.getAttribute('role'),'status');assert.equal(await operation.getAttribute('aria-live'),'polite');count++;
  await schoolOpen(b);await editLayout(b);await b.keyboard.press('Escape');count++;
  for(const locale of ['zh-CN','en-US'])for(const width of [1440,390,320]){
    await b.setViewportSize({width,height:844});await language(b,locale);await schoolOpen(b);
    await selected(b,'i2-devon');await editLayout(b);await b.keyboard.press('Escape');count++;
  }
  await b.setViewportSize({width:390,height:844});await language(b,'zh-CN');
  stage='complete-reopen';console.log('I4b stage: '+stage);await schoolOpen(b);await modal(b).getByRole('button',{name:'标记完成',exact:true}).click();await confirm(b).waitFor();await shot(b,'completion-preview-zh-390');await b.keyboard.press('Escape');await schoolOpen(a);await modal(a).getByRole('button',{name:'标记完成',exact:true}).click();await confirm(a).click();
  await a.getByText('家庭待办已更新',{exact:true}).waitFor();assert((await school(a).textContent()).includes('已完成'));
  await schoolOpen(a);await modal(a).getByRole('button',{name:'恢复未完成',exact:true}).click();await confirm(a).click();
  await a.getByText('家庭待办已更新',{exact:true}).waitFor();assert((await school(a).textContent()).includes('待完成'));assert.equal(await a.locator('article').count(),3);count++;
  stage='keyboard-cancel';console.log('I4b stage: '+stage);await schoolOpen(a);await modal(a).getByRole('button',{name:'标记完成',exact:true}).click();await confirm(a).waitFor();const beforeCancel=writes;
  await a.keyboard.press('Escape');assert(!await modal(a).isVisible());assert.equal(writes,beforeCancel);count++;
  stage='stale';console.log('I4b stage: '+stage);await schoolOpen(a);await modal(a).getByRole('button',{name:'标记完成',exact:true}).click();await confirm(a).waitFor();await command('edit-change');
  await wait(async()=>!await modal(a).isVisible());assert.equal(writes,beforeCancel);count++;
  stage='unknown-reload';console.log('I4b stage: '+stage);await schoolOpen(a);await modal(a).getByRole('button',{name:'标记完成',exact:true}).click();await confirm(a).waitFor();await command('unknown');
  await confirm(a).evaluate(n=>{n.click();n.click();});await a.getByText('结果尚未确认。不要重复提交，请核对最近操作。',{exact:true}).waitFor();assert.equal(writes,beforeCancel+1);
  await nav(a,'pending');await a.locator('.acceptance-status').waitFor();await a.locator('[data-pending="i4a-school"] button').click();assert(!await modal(a).isVisible());count++;
  await a.reload();await a.locator('.stat').first().waitFor();await command('recover');await a.getByRole('button',{name:'核对最近操作',exact:true}).click();
  await a.getByText('家庭待办已更新',{exact:true}).waitFor();assert.equal(writes,beforeCancel+1);count++;
  stage='late-write-gate';console.log('I4b stage: '+stage);await schoolOpen(a);await modal(a).getByRole('button',{name:'恢复未完成',exact:true}).click();await confirm(a).waitFor();
  await a.route('**/api/tasks/edit-confirm',route=>route.abort());await confirm(a).click();await a.getByText('结果尚未确认。不要重复提交，请核对最近操作。',{exact:true}).waitFor();
  await a.unroute('**/api/tasks/edit-confirm');await a.getByRole('button',{name:'核对最近操作',exact:true}).click();
  await a.getByText('已核实本次请求未生效。请重新读取，再独立确认。',{exact:true}).waitFor();assert((await school(a).textContent()).includes('已完成'));count++;
  stage='acceptance-regression';console.log('I4b stage: '+stage);await nav(a,'pending');await a.locator('[data-pending="i4a-school"] button').click();await modal(a).getByRole('button',{name:'确认接受',exact:true}).waitFor();
  await modal(a).getByRole('button',{name:'确认接受',exact:true}).click();await a.getByText('已加入家庭待办',{exact:true}).waitFor();await cards(a,4);count++;
  stage='mobile-language-theme';console.log('I4b stage: '+stage);await b.setViewportSize({width:320,height:844});await b.locator('#secondary-menu>summary').click();await b.locator('#language').selectOption('en-US');await cards(b,3);
  await b.emulateMedia({colorScheme:'dark'});await wait(async()=>await b.locator('html').getAttribute('data-theme')==='dark');
  await schoolOpen(b);await editLayout(b);assert(await modal(b).getByText('Assignee: Devon',{exact:true}).isVisible());await selected(b,'i2-devon');count++;
  await modal(b).getByRole('button',{name:'Reopen task',exact:true}).click();await modal(b).getByRole('button',{name:'Confirm change',exact:true}).waitFor();
  assert(await b.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await shot(b,'reopen-dark-en-320');await b.keyboard.press('Escape');count++;
  await b.setViewportSize({width:390,height:844});await shot(b,'tasks-devon-dark-en-390');
  stage='source-independent';console.log('I4b stage: '+stage);await command('source-revoke');await nav(a,'tasks');await cards(a,4);await schoolOpen(a);await modal(a).getByRole('button',{name:'恢复未完成',exact:true}).click();await confirm(a).click();await a.getByText('家庭待办已更新',{exact:true}).waitFor();count++;
  stage='revoke-clears';console.log('I4b stage: '+stage);await schoolOpen(a);await command('task-revoke clara');await wait(async()=>!await modal(a).isVisible());await cards(a,0);assert.equal(await a.locator('#dialog-body').textContent(),'');count++;
  stage='fault-clears';console.log('I4b stage: '+stage);await command('fail');await b.locator('#reload').click();await b.getByText('Current session or access could not be verified. Check the local test service.').waitFor();assert.equal(await b.locator('article').count(),0);count++;
  assert.equal(errors.length,0);count++;
  child.stdin.write('quit\n');await wait(()=>child.exitCode!==null);
  console.log(count+' I4b actual-origin browser checks passed; disposable fictional SQL only.');
})().catch(error=>{console.error('I4b failed at '+stage+' after '+count+' checks ('+error.name+'; details withheld).');process.exitCode=1;}).finally(async()=>{
  if(child.exitCode===null){child.stdin.write('quit\n');await pause(1000);if(child.exitCode===null)child.kill();}if(browser)await browser.close();
});
