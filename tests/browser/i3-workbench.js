'use strict';
const assert=require('node:assert/strict'),path=require('node:path'),http=require('node:http'),fs=require('node:fs');
const {spawn}=require('node:child_process');const {chromium}=require('playwright');
if(!process.argv.includes('--synthetic-only'))throw Error('Exact synthetic opt-in required');
const root=path.resolve(__dirname,'../..');
const child=spawn(process.env.I3_TEST_PYTHON||path.join(root,'.venv/bin/python'),['-u','tests/browser/i3-fixture-host.py','--synthetic-only'],{cwd:root,stdio:['pipe','pipe','pipe']});
let output='',browser,foreign,count=0,stage='startup';
child.stdout.on('data',b=>{output+=b;});child.stderr.on('data',()=>{});
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(fn){for(let i=0;i<200;i++){if(await fn())return;await pause(100);}throw Error('Synthetic browser expectation timed out');}
async function command(text){const before=output.split('OK').length;child.stdin.write(text+'\n');await wait(()=>output.split('OK').length>before);}
(async()=>{
  await wait(()=>/Open http:\/\/127\.0\.0\.1:\d+\//.test(output));
  const origin=output.match(/Open (http:\/\/127\.0\.0\.1:\d+)\//)[1];
  browser=await chromium.launch({executablePath:process.env.I3_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const ca=await browser.newContext({viewport:{width:1440,height:1000}}),cb=await browser.newContext({viewport:{width:390,height:844}});
  const a=await ca.newPage(),b=await cb.newPage();a.setDefaultTimeout(10000);b.setDefaultTimeout(10000);
  const errors=[],paths=[];
  for(const p of [a,b]){p.on('pageerror',()=>errors.push('browser-error'));p.on('request',r=>paths.push(new URL(r.url()).pathname));}
  async function total(p,n){await wait(async()=>await p.locator('.stat strong').first().textContent().catch(()=>null)===String(n));}
  async function nav(p,key){const button=p.locator('#navigation button[data-view="'+key+'"]');if(await button.isVisible())await button.click();else{await p.locator('#secondary-menu>summary').click();await p.locator('#secondary-body button').filter({hasText:key==='settings'?/设置与隐私|Settings & privacy/:/优惠|Offers/}).click();}}
  async function home(p,n){await nav(p,'home');await total(p,n);}
  async function reload(p){await p.locator('#reload').click();}
  async function approve(p,peer){await p.goto(origin);await p.getByRole('button',{name:'发起请求',exact:true}).click();await wait(async()=>await p.locator('.connection-panel code').count()===1);
    const ticket=await p.locator('.connection-panel code').textContent();await command('approve '+ticket+' '+peer);await total(p,peer==='clara'?3:2);}
  await approve(a,'clara');await approve(b,'devon');count++;
  // Small authorized populations fit one page; desktop cards fill two columns.
  assert.equal(await a.locator('article').count(),3);assert.equal(await b.locator('article').count(),2);
  assert.equal(await a.locator('.connection-paging button').count(),0);
  assert.equal(await b.locator('.connection-paging button').count(),0);count++;
  for(const width of [1440,1024]){await a.setViewportSize({width,height:1000});
    const boxes=await a.locator('article').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width};}));
    assert.equal(boxes[0].y,boxes[1].y);assert(boxes[1].x>boxes[0].x+boxes[0].width);assert(boxes[2].y>boxes[0].y);
    assert(await a.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }await a.setViewportSize({width:1440,height:1000});count++;
  assert.equal(await a.locator('#member-label').textContent(),'当前成员');
  assert.equal(await a.locator('#member-status').textContent(),'Clara');
  assert.equal(await a.locator('.connection-controls select').count(),1);
  assert.equal(await a.locator('#session-member button,#session-member select').count(),0);
  assert(await a.locator('.connection-controls #reload').isVisible());count++;
  const capture=process.argv.includes('--screenshots');
  const images=path.join(root,'docs/screenshots/i3');if(capture)fs.mkdirSync(images,{recursive:true});
  if(capture){await a.screenshot({path:path.join(images,'home-clara-light-desktop.png'),fullPage:true});await b.screenshot({path:path.join(images,'home-devon-light-390.png'),fullPage:true});}
  assert.equal(await a.locator('#member').count(),0);assert.equal(await b.locator('#member').count(),0);
  for(const context of [ca,cb]){const cookie=(await context.cookies()).find(c=>c.name==='__Host-samas-i2');assert(cookie&&cookie.httpOnly&&cookie.secure&&cookie.sameSite==='Strict');}count++;
  assert(!paths.some(p=>/fixtures|model|presentation|snapshot/.test(p)));count++;
  // Observe real, unaccelerated 5-second polls; DOM identity and focus must survive both.
  async function stableAcrossPolls(p,selector,apiPath){
    const node=await p.locator(selector).elementHandle();await node.focus();let polls=0;
    const observed=response=>{if(new URL(response.url()).pathname===apiPath&&response.status()===200)polls++;};
    p.on('response',observed);const started=Date.now();
    try{await wait(async()=>{assert(await node.evaluate(n=>n.isConnected&&document.activeElement===n),'Focus changed: '+selector);return polls>=2&&Date.now()-started>=10100;});
      await pause(150);assert(Date.now()-started>=9500,'Must cross two actual five-second polling rounds');
      assert(await node.evaluate(n=>n.isConnected&&document.activeElement===n),'Focus changed: '+selector);
    }finally{p.off('response',observed);await node.dispose();}
  }
  await Promise.all([
    stableAcrossPolls(a,'#language','/api/tasks'),
    stableAcrossPolls(b,'#navigation button[data-view="tasks"]','/api/tasks')
  ]);count+=2;
  stage='settings-navigation';await nav(b,'settings');stage='settings-ready';await b.locator('#appearance').waitFor();
  stage='open-desktop-detail';
  await a.locator('article button').first().click();await a.getByRole('dialog').waitFor();
  stage='settings-detail-focus';await Promise.all([
    stableAcrossPolls(b,'#appearance','/api/session'),
    stableAcrossPolls(a,'#dialog-body button','/api/tasks')
  ]);assert(await a.getByRole('dialog').isVisible());count+=2;
  // Closing a modal while an automatic check is in flight must not reopen it.
  stage='close-during-poll';let pendingPoll;
  await a.route('**/api/tasks?**',route=>{pendingPoll=route;});stage='await-poll';await wait(()=>!!pendingPoll);
  stage='close-poll-dialog';await a.keyboard.press('Escape');const finished=a.waitForResponse(r=>new URL(r.url()).pathname==='/api/tasks');
  stage='release-poll';await pendingPoll.continue();stage='poll-response';await finished;await a.unroute('**/api/tasks?**');await pause(150);
  assert(!await a.getByRole('dialog').isVisible());assert.equal(await a.locator('#dialog-body').textContent(),'');count++;
  await home(b,2);stage='existing-regressions';
  await a.reload();await total(a,3);count++;
  await a.locator('article button').first().click();await a.getByRole('dialog').waitFor();
  assert.equal(await a.getByRole('dialog').getByRole('button').count(),1);assert((await a.getByRole('dialog').textContent()).includes('只读'));
  if(capture)await a.screenshot({path:path.join(images,'task-readonly-detail-desktop.png'),fullPage:true});
  await a.keyboard.press('Escape');count++;
  await nav(a,'tasks');await a.locator('.connection-filter select').waitFor();
  assert.equal(await a.locator('article').count(),3);assert.equal(await a.locator('.connection-paging button').count(),0);
  if(capture)await a.screenshot({path:path.join(images,'tasks-clara-light-desktop.png'),fullPage:true});
  await a.locator('.connection-filter select').selectOption('home-visit');
  await wait(async()=> (await a.locator('.connection-filter').textContent()).includes('2'));count++;
  await nav(b,'tasks');await b.locator('.connection-filter select').selectOption('home-visit');
  await wait(async()=> (await b.locator('.connection-filter').textContent()).includes('1'));count++;
  await home(a,3);await home(b,2);
  await command('source-revoke clara');await reload(a);await total(a,3);count++;
  await nav(b,'pending');await b.getByText('本轮未连接此功能，不显示离线演示内容。').waitFor();assert.equal(await b.locator('article').count(),0);count++;
  await nav(b,'settings');await b.locator('#appearance').selectOption('dark');assert.equal(await b.locator('html').getAttribute('data-theme'),'dark');
  await b.locator('#appearance').selectOption('system');await b.emulateMedia({colorScheme:'light'});await wait(async()=>await b.locator('html').getAttribute('data-theme')==='light');count++;
  for(const width of [390,320]){await b.setViewportSize({width,height:844});await home(b,2);assert(await b.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    const boxes=await b.locator('article').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y};}));assert.equal(boxes[0].x,boxes[1].x);assert(boxes[1].y>boxes[0].y);
    const heading=await b.locator('article h3').first().boundingBox(),navBox=await b.locator('.nav-main').boundingBox();assert(heading.y+heading.height<navBox.y);
    assert(await b.evaluate(()=>Array.from(document.querySelectorAll('button')).filter(n=>n.getClientRects().length).every(n=>n.scrollWidth<=n.clientWidth+1&&n.getBoundingClientRect().right<=innerWidth+1&&getComputedStyle(n).textOverflow!=='ellipsis')));
    assert(await b.evaluate(()=>Array.from(document.querySelectorAll('article .meta')).every(meta=>{const r=Array.from(meta.children).map(n=>n.getBoundingClientRect());return r.length<2||r[0].right<=r[1].left||r[0].bottom<=r[1].top;})));
  }count++;
  await b.locator('#secondary-menu>summary').click();await b.locator('#language').selectOption('en-US');await total(b,2);assert((await b.locator('main').textContent()).includes('Household overview'));assert.equal(await b.locator('#member-label').textContent(),'Current member');count++;
  if(capture){await b.emulateMedia({colorScheme:'dark'});await b.screenshot({path:path.join(images,'home-devon-dark-en-320.png'),fullPage:true});}
  await home(a,3);
  await a.locator('article button').first().click();await a.getByRole('dialog').waitFor();
  await a.route('**/api/tasks?**',route=>route.fulfill({status:200,contentType:'application/json',body:'{"schema":"wrong"}'}));
  await a.getByText('任务数据格式不匹配，未显示任何任务。').waitFor();
  assert(!await a.getByRole('dialog').isVisible());assert.equal(await a.locator('#dialog-body').textContent(),'');assert.equal(await a.locator('article').count(),0);assert.equal(await a.locator('.stat').count(),0);count++;
  await a.unroute('**/api/tasks?**');await reload(a);await total(a,3);
  let timed;
  await a.route('**/api/tasks?**',route=>{timed=route;});await reload(a);
  await a.getByText('连接失败或超时，未显示旧任务。').waitFor({timeout:10000});assert.equal(await a.locator('article').count(),0);count++;
  await a.unroute('**/api/tasks?**');if(timed)await timed.abort().catch(()=>{});await reload(a);await total(a,3);
  await a.route('**/api/tasks?**',route=>route.abort());await reload(a);await a.getByText('连接失败或超时，未显示旧任务。').waitFor();assert.equal(await a.locator('article').count(),0);count++;
  await a.unroute('**/api/tasks?**');await reload(a);await total(a,3);
  await a.locator('article button').first().click();await a.getByRole('dialog').waitFor();
  await command('fail');await a.getByText('无法验证当前会话或访问权限。请检查本地测试服务。').waitFor();assert.equal(await a.locator('article').count(),0);count++;
  assert.equal(await a.locator('#dialog-body').textContent(),'');assert(!await a.getByRole('dialog').isVisible());
  await command('recover');await reload(a);await total(a,3);
  const oldPage=await a.evaluate(async()=>await(await fetch('/api/tasks?limit=12&offset=0',{headers:{Accept:'application/json','X-Samas-Intent':'local-session'},cache:'no-store'})).text());
  let held;await a.route('**/api/tasks?**',route=>{held=route;});await reload(a);await wait(()=>!!held);
  await command('revoke clara');await a.unroute('**/api/tasks?**');await reload(a);await total(a,0);
  await held.fulfill({status:200,contentType:'application/json',body:oldPage}).catch(()=>{});await pause(200);await total(a,0);
  await a.getByText('当前没有可查看的家庭待办。').waitFor();assert.equal(await a.locator('article').count(),0);await home(b,2);count++;
  await b.locator('article button').first().click();await b.getByRole('dialog').waitFor();
  await command('revoke devon');await total(b,0);assert(!await b.getByRole('dialog').isVisible());
  assert.equal(await b.locator('#dialog-body').textContent(),'');assert.equal(await b.locator('article').count(),0);count++;
  foreign=http.createServer((req,res)=>res.end('<!doctype html><title>Synthetic foreign origin</title>'));await new Promise(r=>foreign.listen(0,'127.0.0.1',r));
  const c=await browser.newPage();await c.goto('http://127.0.0.1:'+foreign.address().port);
  assert(await c.evaluate(async origin=>{try{await fetch(origin+'/api/tasks',{credentials:'include',headers:{'Accept':'application/json','X-Samas-Intent':'local-session'}});return false;}catch(_){return true;}},origin));count++;
  child.stdin.write('quit\n'); // quit intentionally has no OK response.
  await wait(()=>child.exitCode!==null);await wait(async()=> (await b.locator('main').textContent()).includes('Connection failed or timed out'));
  assert.equal(await b.locator('article').count(),0);count++;
  assert.equal(errors.length,0);
  console.log(count+' I3 actual-origin/browser checks passed; fictional SQL tasks only; no secret output.');
})().catch(error=>{console.error('I3 synthetic browser checks failed after '+count+' checks at '+stage+': '+(/^(Focus changed:|Must cross)/.test(error.message)?error.message:error.name)+' (other details withheld).');process.exitCode=1;}).finally(async()=>{
  if(child.exitCode===null){child.stdin.write('quit\n');await pause(1000);if(child.exitCode===null)child.kill();}
  if(browser)await browser.close();if(foreign)foreign.close();
});
