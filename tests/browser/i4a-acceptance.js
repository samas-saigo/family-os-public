'use strict';
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {spawn}=require('node:child_process'),{chromium}=require('playwright');
if(!process.argv.includes('--synthetic-only'))throw Error('Exact synthetic opt-in required');
const root=path.resolve(__dirname,'../..');
const child=spawn(process.env.I4A_TEST_PYTHON||path.join(root,'.venv/bin/python'),['-u','tests/browser/i4a-fixture-host.py','--synthetic-only'],{cwd:root,stdio:['pipe','pipe','pipe']});
let output='',browser,count=0,stage='startup';console.log('I4a stage: '+stage);child.stdout.on('data',b=>output+=b);child.stderr.on('data',()=>{});
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(fn){for(let i=0;i<250;i++){if(await fn())return;await pause(100);}throw Error('Synthetic expectation timed out');}
async function command(text){const before=output.split('OK').length;child.stdin.write(text+'\n');await wait(()=>output.split('OK').length>before);}
(async()=>{
  await wait(()=>/Open http:\/\/127\.0\.0\.1:\d+\//.test(output));const origin=output.match(/Open (http:\/\/127\.0\.0\.1:\d+)\//)[1];
  browser=await chromium.launch({executablePath:process.env.I4A_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const ca=await browser.newContext({viewport:{width:1440,height:1000}}),cb=await browser.newContext({viewport:{width:390,height:844}});
  const a=await ca.newPage(),b=await cb.newPage();for(const p of [a,b])p.setDefaultTimeout(10000);
  const capture=process.argv.includes('--screenshots'),images=path.join(root,'docs/screenshots/i4a');if(capture)fs.mkdirSync(images,{recursive:true});
  const errors=[],requests=[];for(const p of [a,b]){p.on('pageerror',()=>errors.push('browser-error'));p.on('request',r=>requests.push(new URL(r.url()).pathname));}
  const nav=(p,key)=>p.locator('#navigation button[data-view="'+key+'"]').click();
  async function pending(p){await nav(p,'pending');await p.locator('.acceptance-status').waitFor();}
  const card=(p,id)=>p.locator('[data-pending="'+id+'"]');
  async function open(p,id){await card(p,id).getByRole('button').click();await p.getByRole('dialog').getByRole('button',{name:/^(确认接受|Confirm acceptance)$/}).waitFor();}
  async function tasks(p,n){await wait(async()=> (await p.locator('.connection-filter').textContent().catch(()=>''))?.endsWith(String(n)));assert.equal(await p.locator('article').count(),n);}
  async function login(p,peer){await p.goto(origin);await p.getByRole('button',{name:'发起请求',exact:true}).click();await p.locator('.connection-panel code').waitFor();
    await command('approve '+await p.locator('.connection-panel code').textContent()+' '+peer);await p.locator('.stat').first().waitFor();}
  await login(a,'clara');await login(b,'devon');await pending(a);await pending(b);
  assert.equal(await card(a,'i4a-visit').count(),0);assert.equal(await card(b,'i4a-visit').count(),1);
  assert.equal(await card(a,'i4a-offer').count(),0);assert.equal(await card(b,'i4a-notice').count(),0);count++;
  await card(a,'i4a-risk').getByRole('button').click();assert.equal(await a.getByRole('dialog').getByRole('button',{name:'确认接受',exact:true}).count(),0);await a.keyboard.press('Escape');count++;
  stage='cancel';console.log('I4a stage: '+stage);let submitted=0;a.on('request',r=>{if(new URL(r.url()).pathname==='/api/pending/accept')submitted++;});
  if(capture)await a.screenshot({path:path.join(images,'pending-clara-desktop.png'),fullPage:true});
  await open(a,'i4a-school');assert((await a.getByRole('dialog').textContent()).includes('2036-03-14'));
  const closeControl=await a.getByRole('dialog').getByRole('button',{name:'关闭',exact:true}).elementHandle();await closeControl.focus();
  let polls=0;const observed=r=>{if(new URL(r.url()).pathname==='/api/pending'&&r.status()===200)polls++;};a.on('response',observed);const started=Date.now();
  await wait(async()=>{assert(await closeControl.evaluate(n=>n.isConnected&&document.activeElement===n));return polls>=2&&Date.now()-started>=10100;});
  a.off('response',observed);await closeControl.dispose();count++;
  if(capture)await a.screenshot({path:path.join(images,'acceptance-preview-desktop.png'),fullPage:true});
  await a.getByRole('dialog').getByRole('button',{name:'取消',exact:true}).click();assert.equal(submitted,0);
  await nav(a,'tasks');await tasks(a,3);await pending(a);assert.equal(await card(a,'i4a-school').count(),1);count++;
  stage='stale-preview';console.log('I4a stage: '+stage);await open(a,'i4a-school');await command('change');
  await wait(async()=>!await a.getByRole('dialog').isVisible());assert.equal(submitted,0);count++;
  stage='unknown';console.log('I4a stage: '+stage);await open(a,'i4a-school');await command('unknown');
  const confirm=a.getByRole('dialog').getByRole('button',{name:'确认接受',exact:true});await confirm.evaluate(n=>{n.click();n.click();});
  await a.getByText('接受结果尚未确认。不要重复提交；请核对最近一次接受。').waitFor();assert.equal(submitted,1);
  assert.equal(await card(a,'i4a-school').count(),0);await a.getByRole('button',{name:'核对最近一次接受',exact:true}).click();
  await a.getByText('接受结果尚未确认。不要重复提交；请核对最近一次接受。').waitFor();assert.equal(submitted,1);count++;
  stage='reload-recovery';console.log('I4a stage: '+stage);await a.reload();await a.locator('.stat').first().waitFor();await pending(a);await command('recover');
  await a.getByRole('button',{name:'核对最近一次接受',exact:true}).click();await tasks(a,4);assert.equal(submitted,1);
  if(capture)await a.screenshot({path:path.join(images,'accepted-tasks-clara-desktop.png'),fullPage:true});
  await nav(b,'tasks');await tasks(b,3);count++;
  stage='network-loss';console.log('I4a stage: '+stage);await pending(b);await open(b,'i4a-visit');let writes=0;
  b.on('request',r=>{if(new URL(r.url()).pathname==='/api/pending/accept')writes++;});
  await b.route('**/api/pending/accept',route=>route.abort());
  await b.getByRole('dialog').getByRole('button',{name:'确认接受',exact:true}).click();
  await b.getByText('接受结果尚未确认。不要重复提交；请核对最近一次接受。').waitFor();assert.equal(writes,1);
  await b.unroute('**/api/pending/accept');await b.getByRole('button',{name:'核对最近一次接受',exact:true}).click();
  await b.getByText('已核实本次请求未生效。请重新读取；如仍需接受，请重新预览并确认。').waitFor();assert.equal(writes,1);
  await open(b,'i4a-visit');await b.getByRole('dialog').getByRole('button',{name:'确认接受',exact:true}).click();await tasks(b,4);assert.equal(writes,2);
  await nav(a,'tasks');await tasks(a,4);count++;
  stage='mobile-language';console.log('I4a stage: '+stage);await pending(b);
  for(const width of [390,320]){await b.setViewportSize({width,height:844});assert(await b.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  await b.locator('#secondary-menu>summary').click();await b.locator('#language').selectOption('en-US');await b.locator('.acceptance-status').waitFor();
  assert((await b.locator('main').textContent()).includes('More information needed'));count++;
  stage='dark-theme';await b.emulateMedia({colorScheme:'dark'});await wait(async()=>await b.locator('html').getAttribute('data-theme')==='dark');
  await card(b,'i4a-question').getByRole('button').click();assert((await b.getByRole('dialog').textContent()).includes('More information needed'));
  stage='keyboard-dialog';assert(await b.evaluate(()=>document.querySelector('dialog').contains(document.activeElement)));await b.getByRole('dialog').getByRole('button',{name:'Close',exact:true}).focus();await b.keyboard.press('Enter');assert(!await b.getByRole('dialog').isVisible());count++;
  if(capture)await b.screenshot({path:path.join(images,'pending-dark-en-320.png'),fullPage:true});
  stage='failure-clear';console.log('I4a stage: '+stage);await pending(a);await command('fail');await a.locator('#reload').click();await a.getByText('无法验证当前会话或访问权限。请检查本地测试服务。').waitFor();assert.equal(await a.locator('article').count(),0);count++;
  await command('recover');await pending(a);await card(a,'i4a-question').getByRole('button').click();await command('revoke clara');
  await wait(async()=>!await a.getByRole('dialog').isVisible());assert.equal(await a.locator('article').count(),0);assert.equal(await a.locator('#dialog-body').textContent(),'');count++;
  stage='session-bound-feedback';await a.getByRole('button',{name:'核对最近一次接受',exact:true}).click();
  await a.getByText('接受结果尚未确认。不要重复提交；请核对最近一次接受。').waitFor();
  await a.setViewportSize({width:390,height:844});await a.locator('#secondary-menu>summary').click();
  await a.locator('#secondary-body button[data-view="settings"]').click();
  await a.getByRole('button',{name:'注销测试会话',exact:true}).click();await a.getByRole('button',{name:'发起请求',exact:true}).click();
  await a.locator('.connection-panel code').waitFor();await command('approve '+await a.locator('.connection-panel code').textContent()+' devon');
  await a.locator('#appearance').waitFor();await pending(a);assert.equal(await a.locator('#member-status').textContent(),'Devon');
  assert.equal(await card(a,'i3-unaccepted').count(),0);
  assert.equal(await a.getByText('接受结果尚未确认。不要重复提交；请核对最近一次接受。').count(),0);count++;
  assert(!requests.some(p=>/fixtures|model|presentation/.test(p)));assert.equal(errors.length,0);count++;
  child.stdin.write('quit\n');await wait(()=>child.exitCode!==null);await b.getByText('Connection failed or timed out. Previous tasks are not displayed.').waitFor();assert.equal(await b.locator('article').count(),0);count++;
  console.log(count+' I4a actual-origin/browser checks passed; synthetic SQL only; no secrets output.');
})().catch(error=>{console.error('I4a browser checks failed at '+stage+' after '+count+' checks ('+error.name+'; private details withheld).');process.exitCode=1;}).finally(async()=>{
  if(child.exitCode===null){child.stdin.write('quit\n');await pause(1000);if(child.exitCode===null)child.kill();}if(browser)await browser.close();
});
