'use strict';
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs'),{spawn}=require('node:child_process');
if(!process.argv.includes('--synthetic-only'))throw Error('Exact synthetic opt-in required');
const {chromium}=require('playwright'),root=path.resolve(__dirname,'../..'),pause=ms=>new Promise(r=>setTimeout(r,ms));
const child=spawn(process.env.I4B_TEST_PYTHON||path.join(root,'.venv/bin/python'),['-u','tests/browser/i7-fixture-host.py','--synthetic-only','--i9'],{cwd:root,stdio:['pipe','pipe','pipe']});
let output='',browser,stage='startup',layouts=0,checks=0,writes=0;const errors=[],outside=[];
child.stdout.on('data',b=>output+=b);child.stderr.on('data',()=>{});
async function wait(fn){for(let i=0;i<300;i++){if(await fn())return;await pause(100);}throw Error('Synthetic expectation timed out');}
async function command(text){const start=output.length;child.stdin.write(text+'\n');await wait(()=>/OK|UNAVAILABLE/.test(output.slice(start)));assert(!output.slice(start).includes('UNAVAILABLE'));}
(async()=>{
 await wait(()=>/Open http:\/\/127\.0\.0\.1:\d+\//.test(output)&&/Ids .*\n/.test(output));
 const origin=output.match(/Open (http:\/\/127\.0\.0\.1:\d+)\//)[1],ids=JSON.parse(output.match(/Ids (.*)\n/)[1]);
 browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const folder=path.join(root,'docs/screenshots/i9-personal-action-home');
 if(process.argv.includes('--screenshots'))fs.mkdirSync(folder,{recursive:true});
 async function shot(p,name){if(process.argv.includes('--screenshots')){await p.mouse.move(0,0);await p.screenshot({path:path.join(folder,name+'.png'),fullPage:true});}}
 async function session(peer){const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});await context.route('**/*',async route=>{try{if(new URL(route.request().url()).origin!==origin){outside.push('blocked');return await route.abort();}await route.continue();}catch(error){if(!p.isClosed()&&!route.request().failure())errors.push('routing: '+stage);}});const p=await context.newPage();p.setDefaultTimeout(15000);p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(['/api/pending/review-confirm','/api/pending/accept','/api/tasks/edit-confirm'].includes(new URL(r.url()).pathname))writes++;});await p.goto(origin);await p.getByRole('button',{name:'发起请求',exact:true}).click();await p.locator('.connection-panel code').waitFor();await command('approve '+await p.locator('.connection-panel code').textContent()+' '+peer);await p.locator('#i9-mine').waitFor();return p;}
 const a=await session('clara'),b=await session('devon');
 const json=p=>p.evaluate(async()=>{const response=await fetch('/api/action-home',{headers:{Accept:'application/json','X-Samas-Intent':'local-session'},cache:'no-store'});if(!response.ok)throw Error('home unavailable');return response.json();});
 async function nav(p,view){if(view==='settings'&&!await p.locator('[data-view="settings"]').isVisible())await p.locator('#secondary-menu>summary').click();await p.locator('button[data-view="'+view+'"]').click();await p.locator(view==='home'?'#i9-mine':view==='pending'?'#pending-state':view==='settings'?'#appearance':'.responsibility-filters').waitFor();}
 async function reload(p){await p.locator('#reload').click();await p.locator('#i9-mine').waitFor();}
 async function open(p,key='i5-school'){const control=p.locator('[data-i9-open="'+ids[key]+'"]');const followup=await control.evaluate(n=>n.closest('[data-region]').dataset.region==='followup');await control.click();await p.locator(followup?'.personal-handling':'#dialog-body[data-explanation] .i7-dialog-footer').waitFor();}
 const handling=async p=>{if(!await p.locator('.personal-handling').count())await p.getByRole('button',{name:/^(记录处理方式|Record my handling)$/}).click();};
 const save=p=>p.getByRole('button',{name:/^(确认保存|Confirm save)$/});
 async function choose(p,operation){await handling(p);await p.locator('input[value="'+operation+'"]').check();if(operation==='not-applicable')await p.locator('#personal-reason').selectOption('personal-judgment');await wait(()=>save(p).isEnabled());}
 async function confirm(p){await save(p).click();await p.locator('#pending-state').waitFor();await nav(p,'home');}
 async function has(p,region,id){return p.locator('#i9-'+region+' [data-action-id="'+id+'"]').count();}
 await command('process');for(const p of [a,b])await reload(p);
 stage='own-decisions';const beforeA=await json(a),beforeB=await json(b);
 assert.notDeepEqual(beforeA.sections.decisions.items,beforeB.sections.decisions.items);assert(beforeA.sections.decisions.total>3);
 assert.equal(await a.locator('#i9-decisions .i9-card').count(),3);checks++;
 await open(a);const initialWrites=writes;await a.keyboard.press('Escape');assert.equal(writes,initialWrites);
 await open(a);await choose(a,'review');await confirm(a);
 assert.equal((await json(a)).sections.decisions.total,beforeA.sections.decisions.total);assert(await has(a,'decisions',ids['i5-school']));await a.getByText('你已查看，但尚未作出决定。',{exact:true}).waitFor();checks++;
 await open(a);await choose(a,'not-applicable');await confirm(a);assert.equal(await has(a,'decisions',ids['i5-school']),0);
 await nav(a,'pending');await a.locator('#pending-state').selectOption('not-applicable');await a.locator('[data-pending="'+ids['i5-school']+'"]').waitFor();await a.locator('[data-pending="'+ids['i5-school']+'"] button').click();await handling(a);await a.getByRole('button',{name:'恢复处理',exact:true}).click();await wait(()=>a.getByRole('button',{name:'确认恢复处理',exact:true}).isEnabled());await a.getByRole('button',{name:'确认恢复处理',exact:true}).click();await a.locator('#pending-state').waitFor();await nav(a,'home');await a.getByText('你已查看，但尚未作出决定。',{exact:true}).waitFor();checks++;
 await open(a);await choose(a,'defer');await confirm(a);assert(await has(a,'followup',ids['i5-school']));assert.equal(await has(a,'decisions',ids['i5-school']),0);await reload(b);assert(await has(b,'decisions',ids['i5-school']));checks++;
 await open(a);await choose(a,'needs-information');await confirm(a);await a.getByText('你正在等待补充信息。',{exact:true}).waitFor();await shot(a,'clara-followup-zh-CN-light-1440');
 // A confirmed task is independently published; browser uses the original preview/confirm.
 await open(a);await a.getByRole('button',{name:'返回',exact:true}).click();await a.getByRole('button',{name:'查看接受预览',exact:true}).click();await a.getByRole('button',{name:'确认接受',exact:true}).click();await a.locator('.responsibility-filters').waitFor();await nav(a,'home');assert.equal(await has(a,'followup',ids['i5-school']),0);assert.equal((await json(a)).sections.mine.total,beforeA.sections.mine.total+1);checks++;
 // Task assignment remains independent from shared reading; only the region changes.
 const accepted=(await json(a)).sections.mine.items.find(c=>c.item.approved_date==='2040-09-18').item.id;
 await a.locator('[data-i9-open="'+accepted+'"]').click();await a.locator('#edit-assignee').waitFor();await a.locator('#edit-assignee').selectOption('i2-devon');await a.getByRole('button',{name:'调整分工',exact:true}).click();await a.getByRole('button',{name:'确认修改',exact:true}).click();await a.locator('.responsibility-filters').waitFor();await nav(a,'home');assert(await has(a,'collaboration',accepted));await reload(b);assert(await has(b,'mine',accepted));checks++;
 const readWrites=writes;
 for(const [peer,p] of [['clara',a],['devon',b]])for(const language of ['zh-CN','en-US'])for(const theme of ['light','dark']){
  await p.setViewportSize({width:1440,height:1000});await p.locator('#language').selectOption(language);await p.locator('#i9-mine').waitFor();await nav(p,'settings');await p.locator('#appearance').selectOption(theme);await nav(p,'home');
  for(const width of [1440,390,320]){stage=[peer,language,theme,width].join('/');await p.setViewportSize({width,height:width===1440?1000:844});
   const geometry=await p.evaluate(()=>{const rect=n=>{const r=n.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height};};const buttons=[...document.querySelectorAll('.i9-section button,.i9-totals button')];return {overflow:document.documentElement.scrollWidth>innerWidth,cards:[...document.querySelectorAll('#i9-mine .i9-card')].map(rect),nav:rect(document.querySelector('.nav-main')),controls:buttons.map(n=>({...rect(n),clipped:n.scrollWidth>n.clientWidth+1})),member:rect(document.querySelector('#session-member')),toolbar:rect(document.querySelector('.topbar'))};});
   assert(!geometry.overflow);assert(geometry.controls.every(n=>n.width>=44&&n.height>=44&&!n.clipped));assert(geometry.member.left>=0&&geometry.member.right<=width+.5);
   if(width===1440&&geometry.cards.length>1)assert.equal(geometry.cards[0].top,geometry.cards[1].top);
   if(width<731){assert(geometry.cards[0].top<geometry.nav.top);assert(geometry.cards[0].top<844);}
   if((peer==='clara'&&language==='zh-CN')||(peer==='devon'&&language==='en-US'&&theme==='dark'))await shot(p,[peer,language,theme,width].join('-'));layouts++;
  }
 }
 assert.equal(writes,readWrites);checks++;
 stage='keyboard';await a.setViewportSize({width:1440,height:1000});await a.locator('#language').selectOption('zh-CN');await a.locator('#i9-mine').waitFor();const detail=a.locator('#i9-mine [data-i9-open]').first();await detail.focus();await a.keyboard.press('Enter');await a.getByRole('dialog').waitFor();await a.keyboard.press('Escape');assert(!await a.getByRole('dialog').isVisible());checks++;
 // Unchanged successful polls preserve focused navigation. A failure removes cards/counts.
 stage='poll-and-revoke';await a.locator('button[data-view=home]').focus();await pause(10700);assert.equal(await a.evaluate(()=>document.activeElement?.dataset.view),'home');
 await command('source-revoke shared clara');await wait(async()=>!(await json(a)).sections.decisions.items.some(c=>c.item.id===ids['i5-uncertain']));await reload(a);checks++;
 await command('task-revoke clara');await reload(a);assert.equal(await a.locator('#i9-mine .i9-card').count(),0);assert.equal(await a.locator('#i9-collaboration .i9-card').count(),0);assert.equal((await json(b)).sections.mine.total,2);checks++;
 stage='fail-closed';await command('home-fail');await b.locator('#reload').click();await b.locator('.connection-status').waitFor();assert.equal(await b.locator('[data-action-id],.i9-count,.i9-totals').count(),0);assert(!await b.getByRole('dialog').isVisible());await command('home-recover');await reload(b);checks++;
 await b.route('**/api/action-home',r=>r.fulfill({status:200,contentType:'application/json',body:'{}'}));await b.locator('#reload').click();await b.locator('.connection-status').waitFor();assert.equal(await b.locator('[data-action-id]').count(),0);await b.unroute('**/api/action-home');checks++;
 // A late response cannot resurrect Home after navigation/logout or another member's session.
 stage='late-response-session-change';console.log('I9 stage: '+stage);await reload(b);
 let release,arrived,once=true;const seen=new Promise(r=>arrived=r),gate=new Promise(r=>release=r);
 await b.route('**/api/action-home',async route=>{if(!once)return route.continue();once=false;const response=await route.fetch();arrived();await gate;await route.fulfill({response});});
 await b.locator('#reload').click();await seen;await nav(b,'settings');await b.getByRole('button',{name:/^(注销测试会话|Log out test session)$/}).click();await b.locator('.connection-status').waitFor();release();await pause(300);await b.unroute('**/api/action-home');
 assert.equal(await b.locator('[data-action-id],.i9-totals').count(),0);
 await b.getByRole('button',{name:/^(发起请求|Request session)$/}).click();await b.locator('.connection-panel code').waitFor();await command('approve '+await b.locator('.connection-panel code').textContent()+' clara');await b.locator('#appearance').waitFor();await nav(b,'home');assert.equal((await json(b)).member,'i2-clara');assert.equal((await json(b)).sections.mine.total,0);checks++;
 // Missing I9 resources must not downgrade to the older sampled A1 Home.
 stage='missing-home-module';const paths=[];b.on('request',r=>paths.push(new URL(r.url()).pathname));await b.route('**/home.js',r=>r.abort());await b.reload();await b.locator('.connection-status').waitFor();assert.equal(await b.locator('.a1-home,[data-action-id],.i9-totals').count(),0);assert(!paths.includes('/api/tasks'));await b.unroute('**/home.js');await b.reload();await b.locator('#i9-mine').waitFor();checks++;
 // Explicit network failure also clears, rather than replacing with offline data.
 stage='network-failure';console.log('I9 stage: '+stage);await b.route('**/api/action-home',r=>r.abort());await b.locator('#reload').click();await b.locator('.connection-status').waitFor();assert.equal(await b.locator('[data-action-id],.i9-totals').count(),0);checks++;
 assert.deepEqual(errors,[]);assert.deepEqual(outside,[]);console.log(layouts+' I9 real-server peer/language/theme/viewport layouts and '+checks+' state/read/privacy checks passed; no external requests.');
})().catch(e=>{console.error('I9 failed at '+stage+': '+e.message);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(child.exitCode===null){child.stdin.write('quit\n');await pause(1000);if(child.exitCode===null)child.kill();}});
