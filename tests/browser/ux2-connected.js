'use strict';
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs'),{spawn}=require('node:child_process');
if(!process.argv.includes('--synthetic-only'))throw Error('Exact synthetic opt-in required');
const {chromium}=require('playwright'),root=path.resolve(__dirname,'../..'),pause=ms=>new Promise(r=>setTimeout(r,ms));
const child=spawn(process.env.I4B_TEST_PYTHON||path.join(root,'.venv/bin/python'),['-u','tests/browser/i4b-fixture-host.py','--synthetic-only'],{cwd:root,stdio:['pipe','pipe','pipe']});
let output='',browser,count=0,stage='startup',writes=0;const errors=[],requests=[];
child.stdout.on('data',b=>output+=b);child.stderr.on('data',()=>{});
async function wait(fn){for(let i=0;i<300;i++){if(await fn())return;await pause(100);}throw Error('Synthetic expectation timed out');}
async function command(text){const before=output.split('OK').length;child.stdin.write(text+'\n');await wait(()=>output.split('OK').length>before);}
(async()=>{
  await wait(()=>/Open http:\/\/127\.0\.0\.1:\d+\//.test(output));const origin=output.match(/Open (http:\/\/127\.0\.0\.1:\d+)\//)[1];
  browser=await chromium.launch({executablePath:process.env.I4B_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const images=path.join(root,'docs/screenshots/ux2-connected-foundation'),capture=process.argv.includes('--screenshots');if(capture)fs.mkdirSync(images,{recursive:true});
  async function shot(p,name){if(capture){await p.mouse.move(0,0);await p.screenshot({path:path.join(images,name+'.png')});}}
  async function session(peer){
    const context=await browser.newContext({viewport:{width:1440,height:1000},colorScheme:'light',reducedMotion:'reduce'});
    await context.route('**/*',r=>new URL(r.request().url()).origin===origin?r.continue():r.abort());
    const p=await context.newPage();p.setDefaultTimeout(12000);p.on('pageerror',()=>errors.push('browser-error'));
    p.on('request',r=>{const u=new URL(r.url());requests.push(u.origin);if(['/api/tasks/edit-confirm','/api/pending/accept'].includes(u.pathname))writes++;});
    await p.goto(origin);await p.getByRole('button',{name:'发起请求',exact:true}).click();await p.locator('.connection-panel code').waitFor();
    await command('approve '+await p.locator('.connection-panel code').textContent()+' '+peer);await p.locator('.stat').first().waitFor();
    const cookie=(await context.cookies()).find(c=>c.name==='__Host-samas-i2');assert(cookie&&cookie.httpOnly&&cookie.secure&&cookie.sameSite==='Strict');
    assert.equal(await p.locator('.stat strong').first().textContent(),peer==='clara'?'3':'2');
    assert.equal(await p.locator('#member-status').textContent(),peer==='clara'?'Clara':'Devon');return {p,context};
  }
  async function nav(p,key){
    if(['home','tasks','pending','upcoming','security'].includes(key))await p.locator('#navigation button[data-view="'+key+'"]').click();
    else{const menu=p.locator('#secondary-menu');if(!await menu.locator('button[data-view="'+key+'"]').isVisible())await menu.locator('summary').click();await menu.locator('button[data-view="'+key+'"]').click();}
    if(key==='tasks'||key==='home')await p.locator('article').first().waitFor();else if(key==='pending')await p.locator('.acceptance-status').waitFor();
    else await p.waitForFunction(()=>document.querySelector('#member-status').textContent!=='');
  }
  async function language(p,locale){await wait(()=>p.locator('#language-label').evaluate(n=>Boolean(n.closest(matchMedia('(max-width:730px)').matches?'#secondary-body':'.preferences'))));
    const menu=p.locator('#secondary-menu');if(!await p.locator('#language').isVisible())await menu.locator('summary').click();await p.locator('#language').selectOption(locale);
    if(await menu.getAttribute('open')!==null)await menu.locator('summary').click();}
  async function open(p){await p.locator('article').filter({hasText:'2035-06-12'}).getByRole('button',{name:/^(详情|Details)$/}).click();await p.locator('#edit-assignee').waitFor();}
  async function fits(p){
    assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow');
    const failures=await p.evaluate(()=>[...document.querySelectorAll('button,select,summary')].filter(n=>n.checkVisibility()).filter(n=>{const r=n.getBoundingClientRect();return n.scrollWidth>n.clientWidth+1||r.height<44||r.x<-.5||r.right>innerWidth+.5;}).map(n=>n.textContent.trim()));
    assert.deepEqual(failures,[]);
  }
  if(process.argv.includes('--capture-before')){
    assert(capture);const {p,context}=await session('clara');await nav(p,'tasks');await shot(p,'before-tasks-1440');await open(p);await shot(p,'before-detail-1440');await p.keyboard.press('Escape');
    await p.setViewportSize({width:390,height:844});await shot(p,'before-tasks-390');await context.close();console.log('3 actual connected-I4b baseline captures; no regression claim.');return;
  }
  for(const peer of ['clara','devon'])for(const locale of ['zh-CN','en-US'])for(const theme of ['light','dark']){
    // Five draft/preview pairs per session remain below the unchanged server cap.
    const {p,context}=await session(peer);await language(p,locale);await nav(p,'settings');await p.locator('#appearance').selectOption(theme);
    for(const width of [1440,1152,960,390,320]){
      stage=[peer,locale,theme,width].join('/');await p.setViewportSize({width,height:width>730?1000:844});await nav(p,'tasks');await fits(p);
      assert.equal(await p.locator('article').count(),peer==='clara'?3:2);assert.equal(await p.locator('#member-status').textContent(),peer==='clara'?'Clara':'Devon');
      assert.equal(await p.locator('#member-status').locator('select,button').count(),0);
      const origins=[];
      for(const view of ['tasks','home','pending','upcoming','security','offers','settings']){
        await nav(p,view);await fits(p);const box=await p.evaluate(()=>{const w=document.querySelector('.workspace').getBoundingClientRect(),b=document.querySelector('.topbar').getBoundingClientRect(),m=document.querySelector('main').getBoundingClientRect();return {w:w.y,b:b.y,m:m.y};});
        origins.push(box);if(width>730)assert.equal(box.w,0);
        if(width<=730){const controls=p.locator('#main button:visible,#main select:visible');if(await controls.count()){await p.evaluate(()=>scrollTo(0,document.documentElement.scrollHeight));const last=await controls.last().boundingBox(),bottom=await p.locator('.nav-main').boundingBox();assert(last.y+last.height<=bottom.y+.5,'Reachable controls must not sit behind bottom navigation');await p.evaluate(()=>scrollTo(0,0));}}
        if(['upcoming','security','offers'].includes(view))assert.equal(await p.locator('article').count(),0);
      }
      // Active feedback is intentionally a separate live region, not present here.
      assert(origins.every(x=>JSON.stringify(x)===JSON.stringify(origins[0])),'Cross-page top alignment');
      await nav(p,'tasks');
      const name=[peer,locale==='zh-CN'?'zh':'en',theme,width].join('-');
      if((width===1440||width===390||width===320)&&((peer==='clara'&&locale==='zh-CN')||(peer==='devon'&&locale==='en-US')))await shot(p,'tasks-'+name);
      const long=locale==='zh-CN'?'整理虚构学校活动的出行与无障碍安排，并核对需要共同确认的细节（仅布局压力测试）':'Coordinate fictional school arrival, accessibility and accompanying adults; verify details needing joint confirmation (layout stress only)';
      await p.locator('article h3').first().evaluate((n,text)=>{n.textContent=text;},long);await fits(p);await nav(p,'tasks');
      await open(p);await fits(p);assert.equal(await p.locator('#edit-assignee').inputValue(),'joint');assert(await p.getByRole('dialog').getByText('2035-06-12',{exact:true}).isVisible());
      assert(await p.getByRole('dialog').evaluate(n=>n.contains(document.activeElement)),'Focus must remain inside current detail');
      if(width===1440||width===320)if((peer==='clara'&&locale==='zh-CN'&&theme==='light')||(peer==='devon'&&locale==='en-US'&&theme==='dark'))await shot(p,'detail-'+name);
      const change=p.getByRole('dialog').getByRole('button',{name:/^(调整分工|Change assignment)$/});assert(await change.isDisabled());
      await p.locator('#edit-assignee').selectOption('i2-devon');await change.click();await p.getByRole('dialog').getByRole('button',{name:/^(确认修改|Confirm change)$/}).waitFor();await fits(p);
      assert(await p.getByRole('dialog').evaluate(n=>n.contains(document.activeElement)),'Focus must remain inside confirmation');
      await p.keyboard.press('Tab');assert(await p.getByRole('dialog').evaluate(n=>n.contains(document.activeElement)));
      if(width===1440||width===390)if((peer==='clara'&&locale==='zh-CN'&&theme==='light')||(peer==='devon'&&locale==='en-US'&&theme==='dark'))await shot(p,'confirm-'+name);
      await p.keyboard.press('Escape');assert(!await p.getByRole('dialog').isVisible());assert.equal(writes,0,'Inspection/cancellation must not submit');
      await nav(p,'pending');await fits(p);assert.equal(await p.locator('[data-pending="i4a-visit"]').count(),peer==='devon'?1:0);
      if(width===1440||width===390)if(peer==='clara'&&locale==='zh-CN'&&theme==='light')await shot(p,'pending-'+name);
      await nav(p,'settings');await fits(p);assert.equal(await p.locator('#appearance').inputValue(),theme);
      assert.equal(await p.locator('html').getAttribute('data-theme'),theme);
      assert.equal(await p.locator('html').evaluate(n=>getComputedStyle(n).backgroundColor),theme==='light'?'rgb(248, 247, 244)':'rgb(32, 36, 33)');
      assert(await p.evaluate(()=>matchMedia('(prefers-reduced-motion:reduce)').matches));
      const animated=await p.evaluate(()=>[...document.querySelectorAll('button,select')].filter(n=>getComputedStyle(n).transitionDuration!=='0s'||getComputedStyle(n).animationName!=='none').length);assert.equal(animated,0);
      count++;
    }await context.close();
  }
  assert.equal(writes,0);assert.deepEqual(errors,[]);assert(requests.every(o=>o===origin));
  console.log(count+' connected UX2 matrix cases passed; real I4b SessionService/T1 SQL and cookies, 2 adults, 2 languages, 2 themes, 5 widths; zero confirmations submitted.');
})().catch(e=>{console.error('Connected UX2 failed at '+stage+': '+e.message);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(child.exitCode===null){child.stdin.write('quit\n');await pause(1000);if(child.exitCode===null)child.kill();}});
