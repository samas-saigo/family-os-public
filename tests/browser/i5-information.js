'use strict';
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs'),{spawn}=require('node:child_process');
if(!process.argv.includes('--synthetic-only'))throw Error('Exact synthetic opt-in required');
const {chromium}=require('playwright'),root=path.resolve(__dirname,'../..'),pause=ms=>new Promise(r=>setTimeout(r,ms));
const child=spawn(process.env.I4B_TEST_PYTHON||path.join(root,'.venv/bin/python'),['-u','tests/browser/i5-fixture-host.py','--synthetic-only'],{cwd:root,stdio:['pipe','pipe','pipe']});
let output='',browser,stage='startup',matrix=0,checks=0,writes=0;const errors=[],outside=[];
child.stdout.on('data',b=>output+=b);child.stderr.on('data',()=>{});
async function wait(fn){for(let i=0;i<300;i++){if(await fn())return;await pause(100);}throw Error('Synthetic expectation timed out');}
async function command(s){const start=output.length;child.stdin.write(s+'\n');await wait(()=>/OK|UNAVAILABLE/.test(output.slice(start)));assert(!output.slice(start).includes('UNAVAILABLE'),'Controlled fixture experiment failed: '+s.split(' ')[0]);}
(async()=>{
 await wait(()=>/Open http:\/\/127\.0\.0\.1:\d+\//.test(output)&&/Ids .*\n/.test(output));
 const origin=output.match(/Open (http:\/\/127\.0\.0\.1:\d+)\//)[1],ids=JSON.parse(output.match(/Ids (.*)\n/)[1]);
 browser=await chromium.launch({executablePath:process.env.I4B_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const images=path.join(root,'docs/screenshots/i5-information'),capture=process.argv.includes('--screenshots');if(capture)fs.mkdirSync(images,{recursive:true});
 async function shot(p,name){if(capture){await p.mouse.move(0,0);await p.screenshot({path:path.join(images,name+'.png')});}}
 async function session(peer){const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  await context.route('**/*',r=>{if(new URL(r.request().url()).origin!==origin){outside.push('blocked');return r.abort();}return r.continue();});
  const p=await context.newPage();p.setDefaultTimeout(12000);p.on('pageerror',()=>errors.push('page-error'));
  p.on('request',r=>{if(['/api/pending/accept','/api/tasks/edit-confirm'].includes(new URL(r.url()).pathname))writes++;});
  await p.goto(origin);await p.getByRole('button',{name:'发起请求',exact:true}).click();await p.locator('.connection-panel code').waitFor();
  await command('approve '+await p.locator('.connection-panel code').textContent()+' '+peer);await p.locator('.a1-home').waitFor();return p;
 }
 const a=await session('clara'),b=await session('devon');
 async function nav(p,view){const menu=p.locator('#secondary-menu');if(view==='settings'&&!await menu.locator('[data-view="settings"]').isVisible())await menu.locator('summary').click();await p.locator('button[data-view="'+view+'"]').click();if(view==='home')await p.locator('.a1-home').waitFor();else if(view==='tasks')await p.locator('.responsibility-filters').waitFor();else if(view==='pending')await p.locator('.acceptance-status').waitFor();else await p.locator('#appearance').waitFor();}
 async function reload(p,view){await p.locator('#reload').click();if(view==='home')await p.locator('.a1-home').waitFor();else await p.locator('.acceptance-status').waitFor();}
 async function language(p,locale){const menu=p.locator('#secondary-menu');if(!await p.locator('#language').isVisible())await menu.locator('summary').click();await p.locator('#language').selectOption(locale);await p.locator('.a1-home').waitFor();}
 const row=(p,key)=>p.locator('[data-pending="'+ids[key]+'"]');
 async function fits(p){assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(await p.evaluate(()=>[...document.querySelectorAll('button,select,summary')].filter(n=>n.checkVisibility()).filter(n=>{const b=n.getBoundingClientRect();return b.height<44||b.left<-.5||b.right>innerWidth+.5||n.scrollWidth>n.clientWidth+1;}).map(n=>n.tagName)),[]);}
 const initial=await a.locator('[data-home-count="pending"] strong').textContent();await shot(a,'before-process-1440');
 await command('process');await reload(a,'home');await reload(b,'home');
 assert.equal(Number(await a.locator('[data-home-count="pending"] strong').textContent()),Number(initial)+4);assert.equal(await a.locator('[data-home-count="tasks"] strong').textContent(),'3');checks++;
 for(const [peer,p,own,hidden] of [['clara',a,'i5-clara-visit','i5-devon-visit'],['devon',b,'i5-devon-visit','i5-clara-visit']]){
  for(const locale of ['zh-CN','en-US'])for(const theme of ['light','dark']){
   await p.setViewportSize({width:1440,height:1000});await nav(p,'home');await language(p,locale);await nav(p,'settings');await p.locator('#appearance').selectOption(theme);
   for(const width of [1440,390,320]){
    stage=[peer,locale,theme,width].join('/');await p.setViewportSize({width,height:width>730?1000:844});await nav(p,'home');await fits(p);
    assert.equal(await p.locator('[data-home-pending="'+ids[hidden]+'"]').count(),0);
    await nav(p,'pending');await fits(p);assert.equal(await row(p,own).count(),1);assert.equal(await row(p,hidden).count(),0);
    assert.equal(await row(p,'i5-promotion').count(),0);assert.equal(await row(p,'i5-suspicious').count(),0);assert.equal(await row(p,'i5-information').count(),0);
    assert.equal(await row(p,'i5-uncertain').getByRole('button',{name:/^(加入家庭待办|Add household task)$/}).count(),0);
    if(peer==='devon')assert.equal(await row(p,'i5-school').getByRole('button',{name:/^(加入家庭待办|Add household task)$/}).count(),0);
    if((peer==='clara'&&locale==='zh-CN'&&theme==='light')||(peer==='devon'&&locale==='en-US'&&theme==='dark'))await shot(p,'pending-'+peer+'-'+locale+'-'+theme+'-'+width);
    await row(p,'i5-uncertain').getByRole('button').click();assert.equal(await p.getByRole('dialog').getByRole('button',{name:/^(确认接受|Confirm acceptance)$/}).count(),0);await p.keyboard.press('Escape');matrix++;
   }
  }
 }
 assert.equal(writes,0);checks++;
 stage='revoked-generation';await a.setViewportSize({width:1440,height:1000});await nav(a,'home');await language(a,'zh-CN');await nav(a,'pending');
 await command('guard-create');await reload(a,'pending');assert.equal(await row(a,'i5-page-0').getByRole('button',{name:'加入家庭待办',exact:true}).count(),1);
 await command('source-revoke shared clara');await command('source-revoke shared devon');await command('guard-risk');await reload(a,'pending');assert.equal(await row(a,'i5-page-0').count(),0);
 await command('source-grant shared clara');await command('source-grant shared devon');await reload(a,'pending');assert.equal(await row(a,'i5-page-0').count(),1);assert.equal(await row(a,'i5-page-0').getByRole('button',{name:'加入家庭待办',exact:true}).count(),0);
 await shot(a,'regranted-blocked-generation');await command('guard-fresh');await reload(a,'pending');assert.equal(await row(a,'i5-page-0').getByRole('button',{name:'加入家庭待办',exact:true}).count(),1);assert.equal(writes,0);checks++;
 stage='generation';await a.setViewportSize({width:1440,height:1000});await nav(a,'home');await language(a,'zh-CN');await nav(a,'pending');
 await row(a,'i5-school').getByRole('button').click();await a.getByRole('button',{name:'确认接受',exact:true}).waitFor();await a.getByRole('button',{name:'取消',exact:true}).click();assert.equal(writes,0);checks++;
 await row(a,'i5-school').getByRole('button').click();await a.getByRole('button',{name:'确认接受',exact:true}).waitFor();await shot(a,'school-confirm-1440');
 await command('change');await reload(a,'pending');assert(!await a.getByRole('dialog').isVisible());assert.equal(await row(a,'i5-school').getByRole('button',{name:'加入家庭待办',exact:true}).count(),0);
 await command('revert');await reload(a,'pending');await row(a,'i5-school').getByRole('button').click();await a.getByRole('button',{name:'确认接受',exact:true}).waitFor();
 await a.getByRole('button',{name:'确认接受',exact:true}).click();await a.getByText('已加入家庭待办',{exact:true}).waitFor();assert.equal(writes,1);checks++;
 await nav(a,'home');assert.equal(await a.locator('[data-home-count="tasks"] strong').textContent(),'4');await shot(a,'accepted-home-clara-1440');
 await nav(b,'home');assert.equal(await b.locator('[data-home-count="tasks"] strong').textContent(),'3');await shot(b,'accepted-home-devon-320');checks++;
 await nav(a,'tasks');const school=a.locator('article').filter({hasText:'2040-09-18'});await school.getByRole('button',{name:'详情',exact:true}).click();await a.locator('#edit-assignee').waitFor();assert.equal(await a.locator('#edit-assignee').inputValue(),'joint');await a.locator('#edit-assignee').selectOption('i2-devon');await a.getByRole('button',{name:'调整分工',exact:true}).click();await a.getByRole('button',{name:'确认修改',exact:true}).click();await a.getByText('家庭待办已更新',{exact:true}).waitFor();
 await a.locator('[data-responsibility="other"]').click();await wait(()=>a.locator('article').filter({hasText:'2040-09-18'}).count().then(n=>n===1));await shot(a,'assigned-devon-clara-other');
 await nav(b,'tasks');await b.locator('[data-responsibility="mine"]').click();await wait(()=>b.locator('article').filter({hasText:'2040-09-18'}).count().then(n=>n===1));checks++;
 await nav(a,'pending');await command('repeat'); // Same initial generation is historical replay, never resurrects Pending.
 await reload(a,'pending');assert.equal(await row(a,'i5-school').count(),0);checks++;
 stage='unknown';await row(a,'i5-clara-visit').getByRole('button').click();await a.getByRole('button',{name:'确认接受',exact:true}).waitFor();await command('unknown');await a.getByRole('button',{name:'确认接受',exact:true}).click();await a.getByText('结果尚未确认。不要重复提交，请核对最近操作。',{exact:true}).waitFor();await a.reload();await a.locator('.a1-home').waitFor();await command('recover');await a.getByRole('button',{name:'核对最近操作',exact:true}).click();await a.getByText('已加入家庭待办',{exact:true}).waitFor();assert.equal(writes,3);checks++;
 stage='pages';await command('pages');await nav(a,'pending');assert.equal(await a.locator('[data-pending]').count(),12);await a.getByRole('button',{name:'下一页',exact:true}).click();await a.locator('.acceptance-status').waitFor();assert(await a.locator('[data-pending]').count()>0);checks++;
 stage='revocation';await command('source-revoke shared devon');await nav(b,'pending');assert.equal(await row(b,'i5-school').count(),0);assert.equal(await row(b,'i5-mixed').count(),0);assert.equal(await row(b,'i5-devon-visit').count(),1);await shot(b,'source-revoked-devon-pending');await nav(b,'tasks');assert.equal(await b.locator('article').filter({hasText:'2040-09-18'}).count(),1);checks++;
 for(const fault of ['fail','network','invalid']){
  stage=fault;await nav(a,'home');if(fault==='fail')await command('fail');else await a.route('**/api/pending?**',r=>fault==='network'?r.abort():r.fulfill({status:200,contentType:'application/json',body:'{}'}));
  await a.locator('#reload').click();await a.locator('.connection-status').filter({hasText:/无法验证|连接失败|格式不匹配/}).waitFor();assert.equal(await a.locator('article,[data-home-pending]').count(),0);assert(!await a.getByRole('dialog').isVisible());await a.unroute('**/api/pending?**');await command('recover');await reload(a,'home');checks++;
 }
 assert.deepEqual(errors,[]);assert.deepEqual(outside,[]);console.log(matrix+' I5 actual-origin peer/language/theme/width cases and '+checks+' pipeline/safety checks passed; no external requests.');
})().catch(e=>{console.error('I5 failed at '+stage+': '+e.message);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(child.exitCode===null){child.stdin.write('quit\n');await pause(1000);if(child.exitCode===null)child.kill();}});
