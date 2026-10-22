'use strict';
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs'),{spawn}=require('node:child_process');
if(!process.argv.includes('--synthetic-only'))throw Error('Exact synthetic opt-in required');
const {chromium}=require('playwright'),root=path.resolve(__dirname,'../..'),pause=ms=>new Promise(r=>setTimeout(r,ms));
const child=spawn(process.env.I4B_TEST_PYTHON||path.join(root,'.venv/bin/python'),['-u','tests/browser/a1-fixture-host.py','--synthetic-only'],{cwd:root,stdio:['pipe','pipe','pipe']});
let output='',browser,stage='startup',matrix=0,checks=0,writes=0;const errors=[],outside=[];
child.stdout.on('data',b=>output+=b);child.stderr.on('data',()=>{});
async function wait(fn){for(let i=0;i<300;i++){if(await fn())return;await pause(100);}throw Error('Synthetic expectation timed out');}
async function command(s){const start=output.length;child.stdin.write(s+'\n');await wait(()=>/OK|UNAVAILABLE/.test(output.slice(start)));assert(!output.slice(start).includes('UNAVAILABLE'),'Trusted test setup failed');}
(async()=>{
 await wait(()=>/Open http:\/\/127\.0\.0\.1:\d+\//.test(output));const origin=output.match(/Open (http:\/\/127\.0\.0\.1:\d+)\//)[1];
 browser=await chromium.launch({executablePath:process.env.I4B_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const images=path.join(root,'docs/screenshots/ux2-responsibility'),capture=process.argv.includes('--screenshots');if(capture)fs.mkdirSync(images,{recursive:true});
 async function shot(p,name){if(capture){await p.mouse.move(0,0);await p.screenshot({path:path.join(images,name+'.png')});}}
 async function session(peer){
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  await context.route('**/*',r=>{if(new URL(r.request().url()).origin!==origin){outside.push('blocked');return r.abort();}return r.continue();});
  const p=await context.newPage();p.setDefaultTimeout(12000);p.on('pageerror',()=>errors.push('page-error'));
  p.on('request',r=>{if(new URL(r.url()).pathname==='/api/tasks/edit-confirm')writes++;});
  await p.goto(origin);await p.getByRole('button',{name:'发起请求',exact:true}).click();await p.locator('.connection-panel code').waitFor();
  await command('approve '+await p.locator('.connection-panel code').textContent()+' '+peer);await p.locator('.a1-home').waitFor();return {p,context};
 }
 const {p:a,context:ca}=await session('clara'),{p:b,context:cb}=await session('devon');
 async function nav(p,view){
  const menu=p.locator('#secondary-menu');if(view==='settings'&&!await menu.locator('[data-view="settings"]').isVisible())await menu.locator('summary').click();
  await p.locator('button[data-view="'+view+'"]').click();
  if(view==='tasks')await p.locator('.responsibility-filters').waitFor();
  else if(view==='home')await p.locator('.a1-home').waitFor();
  else await p.locator('#appearance').waitFor();
 }
 async function select(p,mode){await p.locator('[data-responsibility="'+mode+'"]').click();await wait(async()=>await p.locator('[data-responsibility="'+mode+'"]').getAttribute('aria-pressed').catch(()=>null)==='true');}
 async function count(p,n){await wait(async()=>(await p.locator('.connection-filter span').textContent().catch(()=>null))?.endsWith('：'+n));}
 async function reload(p){await p.locator('#reload').click();await p.locator('.responsibility-filters').waitFor();}
 async function fits(p){
  assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow');
  assert.deepEqual(await p.evaluate(()=>[...document.querySelectorAll('button,select,summary')].filter(n=>n.checkVisibility()).filter(n=>{const r=n.getBoundingClientRect();return n.scrollWidth>n.clientWidth+1||r.height<44||r.left<-.5||r.right>innerWidth+.5;}).map(n=>n.tagName)),[]);
  const r=await p.locator('.responsibility-filters').boundingBox();assert(r.width<=await p.evaluate(()=>innerWidth));
 }
 async function language(p,locale){const menu=p.locator('#secondary-menu');if(!await p.locator('#language').isVisible())await menu.locator('summary').click();await p.locator('#language').selectOption(locale);await p.locator('.responsibility-filters').waitFor();}
 for(const [peer,p,initial] of [['clara',a,3],['devon',b,2]]){
  for(const locale of ['zh-CN','en-US'])for(const theme of ['light','dark']){
   await p.setViewportSize({width:1440,height:1000});await nav(p,'tasks');await language(p,locale);await nav(p,'settings');await p.locator('#appearance').selectOption(theme);await nav(p,'tasks');
   for(const width of [1440,1152,960,390,320]){
    await p.setViewportSize({width,height:width>730?1000:844});
    for(const [mode,n] of [['all',initial],['mine',peer==='clara'?1:0],['other',0],['joint',2]]){
     stage=[peer,locale,theme,width,mode].join('/');await select(p,mode);await count(p,n);await fits(p);
     assert.equal(await p.locator('article').count(),n);assert.equal(await p.locator('.responsibility-filters button').count(),4);
     assert.equal(await p.locator('[aria-pressed="true"]').count(),1);
     if(!n)assert.match(await p.locator('.empty').textContent(),/筛选|filters/);
     if(width===1440&&locale==='zh-CN'&&theme==='light')await shot(p,peer+'-'+mode+'-1440');
     if(mode==='joint'&&width<=390&&((locale==='zh-CN'&&theme==='light')||(locale==='en-US'&&theme==='dark')))await shot(p,peer+'-'+mode+'-'+locale+'-'+theme+'-'+width);
     matrix++;
    }
   }
  }
 }
 assert.equal(writes,0);checks++;
 stage='keyboard-and-poll';await a.setViewportSize({width:1440,height:1000});await nav(a,'tasks');await language(a,'zh-CN');
 await a.locator('[data-responsibility="joint"]').focus();await a.keyboard.press('Enter');await count(a,2);await wait(()=>a.locator('[data-responsibility="joint"]').evaluate(n=>n===document.activeElement));
 const focused=await a.locator('[data-responsibility="joint"]').elementHandle();await pause(11000);assert(await focused.evaluate(n=>n===document.activeElement));checks++;
 const school=p=>p.locator('article').filter({hasText:'2035-06-12'});
 async function assign(p,value,cancel=false){await school(p).getByRole('button',{name:/^(详情|Details)$/}).click();await p.locator('#edit-assignee').waitFor();assert.equal(await p.locator('#edit-assignee').inputValue(),'joint');await p.locator('#edit-assignee').selectOption(value);await p.getByRole('button',{name:'调整分工',exact:true}).click();await p.getByRole('button',{name:'确认修改',exact:true}).waitFor();await p.getByRole('button',{name:cancel?'取消':'确认修改',exact:true}).click();if(!cancel)await p.getByText('家庭待办已更新',{exact:true}).waitFor();}
 stage='original-edit';await assign(a,'i2-devon',true);assert.equal(writes,0);await assign(a,'i2-devon');assert.equal(writes,1);
 await select(a,'joint');await count(a,1);assert.equal(await school(a).count(),0);
 await select(a,'other');await count(a,1);assert.match(await school(a).textContent(),/Devon/);await shot(a,'clara-after-devon-assignment');
 await select(a,'all');await count(a,3);assert.equal(await school(a).count(),1);
 await nav(b,'tasks');await language(b,'zh-CN');await select(b,'mine');await count(b,1);assert.equal(await school(b).count(),1);await shot(b,'devon-after-assignment');checks++;
 // Home must query the unfiltered v1 endpoint, independent from Tasks conditions.
 stage='home-independent';const reads=[];const watch=r=>{if(new URL(r.url()).pathname==='/api/tasks')reads.push(r.url());};a.on('request',watch);
 await select(a,'mine');await nav(a,'home');assert.equal(await a.locator('[data-home-count="tasks"] strong').textContent(),'3');assert(!reads.at(-1).includes('responsibility='));
 await a.getByRole('button',{name:'查看全部家庭待办',exact:true}).click();await count(a,3);assert.equal(await a.locator('[data-responsibility="all"]').getAttribute('aria-pressed'),'true');a.off('request',watch);checks++;
 stage='balanced-pagination';await command('responsibility');await reload(a);await count(a,45);await reload(b);await count(b,15); // b remains Mine.
 for(const [peer,p,all] of [['clara',a,45],['devon',b,44]]){
  for(const mode of ['all','mine','other','joint']){
   await select(p,mode);const total=Number((await p.locator('.connection-filter span').textContent()).split('：').at(-1));assert(total>=14);
   const ids=[];for(let pages=0;pages<5;pages++){
    ids.push(...await p.locator('article').evaluateAll(ns=>ns.map(n=>n.textContent)));const next=p.getByRole('button',{name:'下一页',exact:true});if(!await next.count())break;await next.click();await p.locator('.responsibility-filters').waitFor();
   }assert.equal(ids.length,total);
   await p.locator('.connection-filter select').selectOption('school-session');await p.locator('.responsibility-filters').waitFor();assert.equal(await p.getByRole('button',{name:'上一页',exact:true}).count(),0);
   await shot(p,peer+'-'+mode+'-combined');await p.locator('.connection-filter select').selectOption('');await p.locator('.responsibility-filters').waitFor();
  }
  await nav(p,'tasks');await count(p,all);checks++;
 }
 // Bind the requested mode/step. A page for the prior filter must clear, not render.
 async function currentBody(mode){return a.evaluate(async mode=>{
  const r=await fetch('/api/tasks?limit=12&offset=0&responsibility='+mode,{credentials:'same-origin',headers:{Accept:'application/json','X-Samas-Intent':'local-session'}});
  if(!r.ok)throw Error('Fictional authorized capture failed');return r.text();
 },mode);}
 stage='wrong-filter';const wrong=JSON.parse(await currentBody('all'));wrong.query.responsibility='other';
 await a.route('**/api/tasks?**',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(wrong)}));
 await a.locator('[data-responsibility="mine"]').click();await a.locator('.connection-status').filter({hasText:/格式不匹配/}).waitFor();assert.equal(await a.locator('article').count(),0);await a.unroute('**/api/tasks?**');await reload(a);checks++;
 stage='late-response';let held=false,release,finished=false,first=true;const gate=new Promise(resolve=>release=resolve),old=await currentBody('joint');
 const hold=async r=>{if(!first)return r.continue();first=false;held=true;await gate;await r.fulfill({status:200,contentType:'application/json',body:old});finished=true;};
 await a.route('**/api/tasks?**',hold);await a.locator('[data-responsibility="joint"]').click();await wait(()=>held);
 await nav(a,'tasks');await count(a,45);release();await wait(()=>finished);await a.unroute('**/api/tasks?**',hold);await pause(200);assert.equal(await a.locator('.a1-home').count(),0);assert.equal(await a.locator('[data-responsibility="all"]').getAttribute('aria-pressed'),'true');await count(a,45);checks++;
 for(const fault of ['abort','timeout','invalid']){
  stage='fault-'+fault;let held;await a.route('**/api/tasks?**',r=>fault==='abort'?r.abort():fault==='invalid'?r.fulfill({status:200,contentType:'application/json',body:'{}'}):(held=r));
  await a.locator('#reload').click();await a.locator('.connection-status').filter({hasText:/格式不匹配|连接失败/}).waitFor();assert.equal(await a.locator('article').count(),0);assert(!await a.getByRole('dialog').isVisible());
  await a.unroute('**/api/tasks?**');if(held)await held.abort().catch(()=>{});await reload(a);checks++;
 }
 stage='revocation';await select(a,'mine');await a.getByRole('button',{name:'下一页',exact:true}).click();await a.locator('.responsibility-filters').waitFor();await command('tasks-revoke clara');await reload(a);await count(a,0);await a.getByRole('button',{name:'上一页',exact:true}).click();await count(a,0);await shot(a,'revoked-empty');await select(a,'all');await count(a,0);assert.match(await a.locator('.empty').textContent(),/家庭待办/);assert.doesNotMatch(await a.locator('.empty').textContent(),/待确认/);await nav(b,'tasks');await count(b,44);checks++;
 stage='member-switch';await select(a,'joint');await ca.addCookies(await cb.cookies());await reload(a);await count(a,44);assert.equal(await a.locator('[data-responsibility="all"]').getAttribute('aria-pressed'),'true');assert.equal(await a.locator('#member-status').textContent(),'Devon');checks++;
 await command('member-revoke devon');await a.locator('#reload').click();await a.locator('.connection-status').filter({hasText:/无法验证/}).waitFor();assert.equal(await a.locator('article').count(),0);checks++;
 assert.deepEqual(errors,[]);assert.deepEqual(outside,[]);assert.equal(writes,1);
 console.log(matrix+' actual-origin filter/layout combinations and '+checks+' safety/interaction checks passed. Fictional SQL only; no external requests.');
})().catch(e=>{console.error('Responsibility failed at '+stage+': '+e.message);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(child.exitCode===null){child.stdin.write('quit\n');await pause(1000);if(child.exitCode===null)child.kill();}});
