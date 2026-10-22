'use strict';
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs'),{spawn}=require('node:child_process');
if(!process.argv.includes('--synthetic-only'))throw Error('Exact synthetic opt-in required');
const {chromium}=require('playwright'),root=path.resolve(__dirname,'../..'),pause=ms=>new Promise(r=>setTimeout(r,ms));
const child=spawn(process.env.I4B_TEST_PYTHON||path.join(root,'.venv/bin/python'),['-u','tests/browser/i6-fixture-host.py','--synthetic-only'],{cwd:root,stdio:['pipe','pipe','pipe']});
let output='',browser,stage='startup',layouts=0,checks=0,writes=0,previews=0;const errors=[],outside=[];
child.stdout.on('data',b=>output+=b);child.stderr.on('data',()=>{});
async function wait(fn){for(let i=0;i<300;i++){if(await fn())return;await pause(100);}throw Error('Synthetic expectation timed out');}
async function command(s){const start=output.length;child.stdin.write(s+'\n');await wait(()=>/OK|UNAVAILABLE/.test(output.slice(start)));assert(!output.slice(start).includes('UNAVAILABLE'),'Controlled fixture experiment failed: '+s.split(' ')[0]);}
(async()=>{
 await wait(()=>/Open http:\/\/127\.0\.0\.1:\d+\//.test(output)&&/Ids .*\n/.test(output));
 const origin=output.match(/Open (http:\/\/127\.0\.0\.1:\d+)\//)[1],ids=JSON.parse(output.match(/Ids (.*)\n/)[1]);
 browser=await chromium.launch({executablePath:process.env.I4B_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const images=path.join(root,'docs/screenshots/i6-explanations'),capture=process.argv.includes('--screenshots');if(capture)fs.mkdirSync(images,{recursive:true});
 async function shot(p,name){if(capture){await p.mouse.move(0,0);await p.screenshot({path:path.join(images,name+'.png')});}}
 async function session(peer){const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  await context.route('**/*',r=>{if(new URL(r.request().url()).origin!==origin){outside.push('blocked');return r.abort();}return r.continue();});
  const p=await context.newPage();p.setDefaultTimeout(15000);p.on('pageerror',()=>errors.push('page-error'));
  p.on('request',r=>{const q=new URL(r.url()).pathname;if(q==='/api/pending/accept')writes++;if(q==='/api/pending/preview')previews++;});
  await p.goto(origin);await p.getByRole('button',{name:'发起请求',exact:true}).click();await p.locator('.connection-panel code').waitFor();
  await command('approve '+await p.locator('.connection-panel code').textContent()+' '+peer);await p.locator('.a1-home').waitFor();return p;
 }
 const a=await session('clara'),b=await session('devon');
 async function nav(p,view){const menu=p.locator('#secondary-menu');if(view==='settings'&&!await menu.locator('[data-view="settings"]').isVisible())await menu.locator('summary').click();await p.locator('button[data-view="'+view+'"]').click();if(view==='home')await p.locator('.a1-home').waitFor();else if(view==='pending')await p.locator('.acceptance-status').waitFor();else if(view==='tasks')await p.locator('.responsibility-filters').waitFor();else await p.locator('#appearance').waitFor();}
 async function locale(p,value){await nav(p,'home');if(!await p.locator('#language').isVisible())await p.locator('#secondary-menu>summary').click();await p.locator('#language').selectOption(value);await p.locator('.a1-home').waitFor();}
 const row=(p,key)=>p.locator('[data-pending="'+ids[key]+'"]');
 async function open(p,key){await row(p,key).getByRole('button').click();await p.locator('#dialog-body[data-explanation="'+ids[key]+'"] section').first().waitFor();}
 async function close(p){await p.keyboard.press('Escape');assert(!await p.getByRole('dialog').isVisible());assert.equal(await p.locator('#dialog-body[data-explanation]').count(),0);}
 async function reload(p){await p.locator('#reload').click();await p.locator('.acceptance-status').waitFor();}
 async function fits(p){assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(await p.evaluate(()=>[...document.querySelectorAll('dialog button')].filter(n=>n.checkVisibility()).filter(n=>{const b=n.getBoundingClientRect();return b.height<44||b.left<-.5||b.right>innerWidth+.5||n.scrollWidth>n.clientWidth+1;}).map(n=>n.tagName)),[]);}
 await command('process');
 for(const [peer,p,own,hidden] of [['clara',a,'i5-clara-visit','i5-devon-visit'],['devon',b,'i5-devon-visit','i5-clara-visit']])for(const language of ['zh-CN','en-US'])for(const theme of ['light','dark']){
  await p.setViewportSize({width:1440,height:1000});await locale(p,language);await nav(p,'settings');await p.locator('#appearance').selectOption(theme);await nav(p,'pending');
  for(const width of [1440,390,320]){
   stage=[peer,language,theme,width].join('/');await p.setViewportSize({width,height:width>730?1000:844});await fits(p);assert.equal(await row(p,hidden).count(),0);
   await open(p,peer==='clara'?'i5-school':own);await fits(p);assert.equal(await p.getByRole('heading',{name:language==='zh-CN'?'发生了什么':'What happened',exact:true}).count(),1);
   assert.equal(await p.getByRole('button',{name:/^(确认接受|Confirm acceptance)$/}).count(),0);
   if((language==='zh-CN'&&theme==='light')||(language==='en-US'&&theme==='dark'))await shot(p,peer+'-'+language+'-'+theme+'-'+width);
   const within=await p.evaluate(()=>document.querySelector('dialog').contains(document.activeElement));assert(within);await p.keyboard.press('Tab');assert.equal(await p.evaluate(()=>document.activeElement.textContent),language==='zh-CN'?'查看接受预览':'Review acceptance preview');const focus=await p.evaluate(()=>{const b=document.activeElement.getBoundingClientRect();return b.top>=0&&b.bottom<=innerHeight;});assert(focus);await p.keyboard.press('Shift+Tab');await close(p);layouts++;
  }
 }
 assert.equal(writes,0);assert.equal(previews,0);checks++;
 stage='legacy-preview';await a.setViewportSize({width:1440,height:1000});await locale(a,'zh-CN');await nav(a,'pending');await a.locator('[data-pending="i4a-school"]').getByRole('button').click();await a.getByRole('button',{name:'确认接受',exact:true}).waitFor();await a.getByRole('button',{name:'取消',exact:true}).click();assert.equal(writes,0);checks++;
 stage='conflict';await a.setViewportSize({width:1440,height:1000});await locale(a,'zh-CN');await nav(a,'pending');await open(a,'i5-uncertain');await a.getByText('依据冲突，不能据此确定需要执行的行动。',{exact:true}).waitFor();assert.equal(await a.getByRole('button',{name:'查看接受预览',exact:true}).count(),0);await shot(a,'conflicting-evidence');await close(a);checks++;
 stage='mixed';await open(a,'i5-mixed');await a.getByText('重要服务部分仍需核实；促销和优惠有效期不构成家庭义务。',{exact:true}).waitFor();assert.equal(await a.getByRole('button',{name:'查看接受预览',exact:true}).count(),0);await close(a);checks++;
 stage='version';await open(a,'i5-school');await command('change');await wait(()=>a.getByRole('dialog').isVisible().then(v=>!v));await open(a,'i5-school');assert.equal(await a.getByRole('button',{name:'查看接受预览',exact:true}).count(),0);await close(a);await command('revert');await reload(a);await open(a,'i5-school');await a.getByRole('button',{name:'查看接受预览',exact:true}).waitFor();await close(a);checks++;
 stage='blocked';await open(a,'i5-school');await command('source-revoke shared clara');await command('source-revoke shared devon');await command('blocked');await wait(()=>a.getByRole('dialog').isVisible().then(v=>!v));assert.equal(await row(a,'i5-school').count(),0);
 await command('source-grant shared clara');await command('source-grant shared devon');await reload(a);await open(a,'i5-school');await a.getByText('本代输入未形成可用的业务解释。',{exact:true}).waitFor();assert.equal(await a.getByRole('button',{name:'查看接受预览',exact:true}).count(),0);await shot(a,'blocked-after-regrant');await close(a);await command('fresh');await reload(a);checks++;
 stage='late';let release,ready;const arrived=new Promise(r=>ready=r),gate=new Promise(r=>release=r);let once=true;
 await a.route('**/api/pending/explanation?**',async route=>{if(!once)return route.continue();once=false;const response=await route.fetch();ready();await gate;try{await route.fulfill({response});}catch(_){}});
 await row(a,'i5-school').getByRole('button').click();await arrived;await close(a);await open(a,'i5-uncertain');release();await pause(300);assert.equal(await a.locator('#dialog-body').getByText('依据冲突，不能据此确定需要执行的行动。',{exact:true}).count(),1);await close(a);await a.unroute('**/api/pending/explanation?**');checks++;
 stage='faults';for(const fault of ['network','invalid','timeout','service']){
  if(fault==='service')await command('fail');else await a.route('**/api/pending/explanation?**',async r=>{if(fault==='timeout'){await pause(5500);try{await r.abort();}catch(_){}return;}return fault==='network'?r.abort():r.fulfill({status:200,contentType:'application/json',body:'{}'});});
  await row(a,'i5-school').getByRole('button').click();await a.getByText('当前无法读取说明，请重新读取待确认列表。',{exact:true}).waitFor();assert.equal(await a.locator('#dialog-body section').count(),0);await close(a);await a.unroute('**/api/pending/explanation?**');await command('recover');checks++;
 }
 stage='security-scope';await locale(b,'zh-CN');await nav(b,'pending');await open(b,'i5-school');await b.getByText('当前测试评估未标记风险，不代表现实安全。',{exact:true}).waitFor();await command('security-revoke shared devon');await wait(()=>b.getByRole('dialog').isVisible().then(v=>!v));await open(b,'i5-school');assert.equal(await b.getByText('当前无法确认是否可接受。',{exact:true}).count(),1);assert.equal(await b.getByText('当前测试评估未标记风险，不代表现实安全。',{exact:true}).count(),0);await close(b);checks++;
 stage='accept';await open(a,'i5-school');await a.getByRole('button',{name:'查看接受预览',exact:true}).click();await a.getByRole('button',{name:'确认接受',exact:true}).waitFor();await a.getByRole('button',{name:'取消',exact:true}).click();assert.equal(writes,0);await open(a,'i5-school');await a.getByRole('button',{name:'查看接受预览',exact:true}).click();await a.getByRole('button',{name:'确认接受',exact:true}).click();await a.getByText('已加入家庭待办',{exact:true}).waitFor();assert.equal(writes,1);checks++;
 stage='session-change';const c=await session('clara');await nav(c,'pending');let resume,observed;const held=new Promise(r=>observed=r),hold=new Promise(r=>resume=r);let intercept=true;
 await c.route('**/api/pending/explanation?**',async route=>{if(!intercept)return route.continue();intercept=false;const response=await route.fetch();observed();await hold;try{await route.fulfill({response});}catch(_){}});
 await row(c,'i5-clara-visit').getByRole('button').click();await held;
 await c.evaluate(async()=>{await fetch('/api/logout',{method:'POST',headers:{'Content-Type':'application/json','X-Samas-Intent':'local-session'},body:'{}'});});
 await wait(()=>c.getByRole('dialog').isVisible().then(v=>!v));await c.getByRole('button',{name:'发起请求',exact:true}).click();await c.locator('.connection-panel code').waitFor();await command('approve '+await c.locator('.connection-panel code').textContent()+' devon');await c.locator('#member-status').filter({hasText:'Devon'}).waitFor();resume();await pause(300);assert.equal(await c.locator('#dialog-body[data-explanation]').count(),0);await nav(c,'pending');assert.equal(await row(c,'i5-clara-visit').count(),0);await c.context().close();checks++;
 stage='private-shared-task';await nav(a,'pending');await open(a,'i5-clara-visit');await a.getByRole('button',{name:'查看接受预览',exact:true}).click();await command('unknown');await a.getByRole('button',{name:'确认接受',exact:true}).click();await a.getByText('结果尚未确认。不要重复提交，请核对最近操作。',{exact:true}).waitFor();await a.reload();await a.locator('.a1-home').waitFor();await command('recover');await a.getByRole('button',{name:'核对最近操作',exact:true}).click();await a.getByText('已加入家庭待办',{exact:true}).waitFor();assert.equal(writes,2);await nav(b,'home');assert.equal(await b.locator('[data-home-count="tasks"] strong').textContent(),'4');
 const denial=await b.evaluate(async id=>{const res=await fetch('/api/pending/explanation?id='+id+'&revision=1',{headers:{Accept:'application/json','X-Samas-Intent':'local-session'}});return {status:res.status,body:await res.text()};},ids['i5-clara-visit']);assert.equal(denial.status,400);assert.equal(denial.body,'{"error":"local_session_unavailable"}');checks++;
 stage='pending-revoke';await nav(b,'pending');let releaseRevoked,seenRevoked;const saved=new Promise(r=>seenRevoked=r),holdRevoked=new Promise(r=>releaseRevoked=r);let firstRevoked=true;
 await b.route('**/api/pending/explanation?**',async route=>{if(!firstRevoked)return route.continue();firstRevoked=false;const response=await route.fetch();seenRevoked();await holdRevoked;try{await route.fulfill({response});}catch(_){}});
 await row(b,'i5-devon-visit').getByRole('button').click();await saved;await command('pending-revoke devon');await wait(()=>b.getByRole('dialog').isVisible().then(v=>!v));releaseRevoked();await pause(300);assert.equal(await row(b,'i5-devon-visit').count(),0);assert.equal(await b.locator('#dialog-body[data-explanation]').count(),0);await b.unroute('**/api/pending/explanation?**');checks++;
 stage='binding-revoke';await nav(a,'pending');await open(a,'i5-uncertain');await command('binding-revoke clara');await wait(()=>a.getByRole('dialog').isVisible().then(v=>!v));assert.equal(await a.locator('[data-pending]').count(),0);assert.equal(await a.locator('#dialog-body[data-explanation]').count(),0);checks++;
 assert.deepEqual(errors,[]);assert.deepEqual(outside,[]);console.log(layouts+' I6 actual-origin layouts and '+checks+' explanation/privacy/interaction checks passed; no external requests.');
})().catch(e=>{console.error('I6 failed at '+stage+': '+e.message);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(child.exitCode===null){child.stdin.write('quit\n');await pause(1000);if(child.exitCode===null)child.kill();}});
