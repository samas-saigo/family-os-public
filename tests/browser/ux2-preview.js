'use strict';
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs'),http=require('node:http');
const {chromium}=require('playwright');
if(!process.argv.includes('--synthetic-only'))throw Error('Explicit synthetic opt-in required');
const root=path.resolve(__dirname,'../..'),ui=path.join(root,'prototypes/ux2-design-preview');
const images=path.join(root,'docs/screenshots/ux2-calm-premium'),capture=process.argv.includes('--screenshots');
const {copy}=require(path.join(ui,'preview.js'));let browser,server,count=0,stage='startup';
const t=(locale,key)=>copy[locale][key];
(async()=>{
  // Test-only renderer: this environment blocks file://. No policy/CSP bypass.
  const assets=new Map([['/','index.html'],['/styles.css','styles.css'],['/preview.js','preview.js']].map(([url,file])=>[url,fs.readFileSync(path.join(ui,file))]));
  server=http.createServer((req,res)=>{if(req.method!=='GET'||!assets.has(req.url)){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',req.url.endsWith('.css')?'text/css':req.url.endsWith('.js')?'text/javascript':'text/html; charset=utf-8');res.end(assets.get(req.url));});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;
  browser=await chromium.launch({executablePath:process.env.UX2_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const p=await context.newPage(),errors=[],requests=[];p.setDefaultTimeout(8000);
  p.on('pageerror',e=>errors.push(e.name));p.on('request',r=>requests.push(r.url()));
  await context.route('**/*',route=>new URL(route.request().url()).origin===origin&&assets.has(new URL(route.request().url()).pathname)?route.continue():route.abort());
  const go=key=>p.locator('#navigation button[data-view="'+key+'"]').click();
  const dialog=p.locator('#dialog'),body=p.locator('#dialog-content');
  const close=()=>p.keyboard.press('Escape');
  async function language(locale){
    await p.waitForFunction(()=>Boolean(document.querySelector('#language').closest(matchMedia('(max-width:730px)').matches?'#more-content':'#desktop-language')));
    if(!await p.locator('#language').isVisible())await p.locator('#more-label').click();
    await p.locator('#language').selectOption(locale);
  }
  async function appearance(value){
    if(await p.locator('#secondary').isVisible())await p.locator('#secondary button').filter({hasText:/^(设置与隐私|Settings & privacy)$/}).click();
    else {await p.locator('#more-label').click();await p.locator('#more-content button').filter({hasText:/^(设置与隐私|Settings & privacy)$/}).click();}
    await p.locator('#appearance').selectOption(value);
  }
  async function fits(){
    assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    const failures=await p.evaluate(()=>[...document.querySelectorAll('button,select,input,summary')].filter(n=>{
      const r=n.getBoundingClientRect();return r.width&&r.height&&getComputedStyle(n).visibility!=='hidden'&&
        (n.scrollWidth>n.clientWidth+1||r.height<44||r.left<-.5||r.right>innerWidth+.5);
    }).map(n=>n.tagName+':'+n.textContent.trim().slice(0,30)));
    assert.deepEqual(failures,[]);
  }
  async function shot(name){if(capture){fs.mkdirSync(images,{recursive:true});await p.screenshot({path:path.join(images,name+'.png')});}}
  await p.goto(origin);
  await p.locator('[data-task="visit"]').waitFor();assert.equal(errors.length,0);count++;
  for(const locale of ['zh-CN','en-US'])for(const theme of ['light','dark'])for(const width of [1440,390,320]){
    stage=[locale,theme,width].join('/');await p.setViewportSize({width,height:width===1440?1000:844});
    await language(locale);await appearance(theme);await go('home');await fits();
    const first=await p.locator('[data-task="visit"] h3').boundingBox(),firstAction=await p.locator('[data-task="visit"] button').boundingBox();const nav=await p.locator('#navigation').boundingBox();
    assert(first.y+first.height<(width<731?nav.y:1000));assert(firstAction.y+firstAction.height<(width<731?nav.y:1000));assert.equal(await p.locator('#main [data-task]').count(),2);
    assert(!await p.locator('#main').textContent().then(s=>s.includes(t(locale,'offerTitle'))));
    if(locale==='zh-CN')await shot('a1-home-'+theme+'-'+width);count++;
    await p.locator('[data-design-choice="a2"]').click();await fits();
    const hubFirst=await p.locator('[data-task="visit"] h3').boundingBox();assert(hubFirst.y+hubFirst.height<(width<731?nav.y:1000));const hubAction=await p.locator('[data-task="visit"] button').boundingBox();assert(hubAction.y+hubAction.height<(width<731?nav.y:1000));
    assert.equal(await p.locator('#main [data-task]').count(),2);assert.equal(await p.locator('.action-board .home-question').count(),1);
    assert(!await p.locator('#main').textContent().then(s=>s.includes(t(locale,'offerTitle'))));
    if(locale==='zh-CN')await shot('a2-home-'+theme+'-'+width);
    if(locale==='en-US'&&theme==='dark'&&width===320)await shot('a2-home-en-dark-320');
    await p.locator('[data-task="visit"] h3').evaluate((n,text)=>{n.textContent=text;},t(locale,'longTitle'));await fits();
    const titleBox=await p.locator('[data-task="visit"] h3').boundingBox(),actionBox=await p.locator('[data-task="visit"] button').boundingBox();assert(titleBox.x+titleBox.width<=actionBox.x);
    await p.locator('[data-design-choice="a1"]').click();count++;
    await go('tasks');await fits();assert.equal(await p.locator('[data-task]').count(),3);
    assert.equal(await p.locator('.filter-proposal button:disabled').count(),4);
    if(locale==='zh-CN'&&theme==='light')await shot('tasks-light-'+width);count++;
    await p.locator('[data-task="school"] button').click();await fits();
    assert.equal(await p.locator('#assignee').inputValue(),'devon');assert(await body.getByRole('button',{name:t(locale,'assign'),exact:true}).isDisabled());
    if((locale==='zh-CN'&&theme==='light')||(locale==='en-US'&&theme==='dark'&&width===320))await shot('detail-'+(locale==='zh-CN'?'zh':'en')+'-'+theme+'-'+width);
    await p.locator('#assignee').selectOption('clara');assert(await body.getByRole('button',{name:t(locale,'assign'),exact:true}).isEnabled());
    await p.locator('#assignee').selectOption('devon');assert(await body.getByRole('button',{name:t(locale,'assign'),exact:true}).isDisabled());
    await p.locator('#assignee').selectOption('clara');await body.getByRole('button',{name:t(locale,'assign'),exact:true}).click();await fits();
    assert(await dialog.evaluate(n=>n.contains(document.activeElement)));await p.keyboard.press('Tab');assert(await dialog.evaluate(n=>n.contains(document.activeElement)));
    if(locale==='zh-CN'&&theme==='light')await shot('confirm-light-'+width);
    await body.getByRole('button',{name:t(locale,'cancel'),exact:true}).click();assert(!await dialog.isVisible());
    await p.locator('[data-task="school"] button').click();assert.equal(await p.locator('#assignee').inputValue(),'devon');
    await close();count++;
    await go('pending');await fits();assert.equal(await p.locator('.pending-item').count(),2);
    assert(await p.getByText(t(locale,'information'),{exact:true}).isVisible());
    if(locale==='zh-CN'&&theme==='light')await shot('pending-light-'+width);
    await p.locator('.buckets button').last().click();assert.equal(await p.locator('.pending-item').count(),1);assert(await p.getByText(t(locale,'laterQuestion'),{exact:true}).isVisible());
    await p.locator('.buckets button').first().click();count++;
  }
  stage='toolbar-geometry';
  for(const locale of ['zh-CN','en-US'])for(const theme of ['light','dark'])for(const width of [1440,1152,960,390,320]){
    await p.setViewportSize({width,height:width>730?1000:844});await language(locale);await appearance(theme);await go('home');
    const alignment=await p.evaluate(()=>{
      const box=s=>{const n=document.querySelector(s),r=n.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,cy:r.y+r.height/2};};
      const labels=['.top-controls>.viewer','.language>span','#language'].map(box);
      const proposal=box('#proposal-label');return {labels,proposal,bar:box('.topbar')};
    });
    if(width>730){
      const ys=alignment.labels.map(n=>n.cy);assert(Math.max(...ys)-Math.min(...ys)<=1);
      for(let i=1;i<alignment.labels.length;i++)assert(alignment.labels[i].x>=alignment.labels[i-1].right);
      if(width>1000)assert(Math.abs(alignment.proposal.cy-ys[0])<=1);
      else assert(alignment.proposal.bottom<=alignment.labels[0].y);
    }else{
      await p.locator('#more-label').click();await fits();
      assert(await p.locator('#more-content .viewer').isVisible());
      const menu=await p.locator('#more-content').boundingBox(),lang=await p.locator('#language').boundingBox();
      assert(lang.x>=menu.x&&lang.x+lang.width<=menu.x+menu.width);
    }
    await fits();
    if(locale==='zh-CN'&&theme==='light')await shot('toolbar-after-'+width);
    if(locale==='en-US'&&theme==='dark'&&width===1152)await shot('toolbar-after-en-dark-1152');
    if(width<731)await p.locator('#more-label').click();count++;
  }
  stage='home-navigation-and-reset';await p.setViewportSize({width:390,height:844});await language('zh-CN');await appearance('light');await go('home');
  await p.locator('[data-design-choice="a2"]').click();await p.locator('[data-task="visit"] button').click();
  assert(await body.getByText(copy['zh-CN'].noDate,{exact:true}).isVisible());await close();
  for(const target of ['tasks','pending','calendar','security']){await p.locator('.home-index button').nth(['tasks','pending','calendar','security'].indexOf(target)).click();assert.equal(await p.locator('#main').getAttribute('data-view'),target);await go('home');}
  assert.equal(await p.locator('.home-design').getAttribute('data-design'),'a2');
  await p.reload();assert.equal(await p.locator('.home-design').getAttribute('data-design'),'a1');count++;
  const baselineArg=process.argv.indexOf('--baseline-assets');
  if(baselineArg!==-1){
    stage='accepted-component-layout-baseline';const saved=new Map(assets),shots=new Map();
    for(const baseline of [false,true]){
      if(baseline){for(const [url,file] of [['/','index.html'],['/styles.css','styles.css'],['/preview.js','preview.js']])assets.set(url,fs.readFileSync(path.join(process.argv[baselineArg+1],file)));}
      await p.reload();
      for(const theme of ['light','dark'])for(const width of [1440,390,320]){
        await p.setViewportSize({width,height:width===1440?1000:844});await appearance(theme);
        for(const state of ['tasks','pending','detail']){
          await go(state==='detail'?'tasks':state);if(state==='detail')await p.locator('[data-task="school"] button').click();
          await p.mouse.move(0,0);const key=[theme,width,state].join('/');
          // The shared top-origin fix intentionally moves whole pages. Compare
          // internal geometry/styles, not glyph rasterization at old subpixels.
          const snapshot=await p.locator(state==='detail'?'#dialog-content':'#main').evaluate(root=>{
            const origin=root.getBoundingClientRect(),properties=['fontFamily','fontSize','fontWeight','lineHeight','color','backgroundColor','borderWidth','borderColor','borderRadius','padding','margin','gap','display','gridTemplateColumns'];
            return [root,...root.querySelectorAll('*')].filter(n=>n.checkVisibility()).map(n=>{
              const r=n.getBoundingClientRect(),s=getComputedStyle(n);
              return {kind:n.tagName,classes:n.className,rect:[r.x-origin.x,r.y-origin.y,r.width,r.height],style:properties.map(k=>s[k])};
            });
          });
          if(!baseline)shots.set(key,snapshot);else{
            const expected=shots.get(key);assert.equal(snapshot.length,expected.length,key);
            snapshot.forEach((node,i)=>{assert.deepEqual([node.kind,node.classes,node.style],[expected[i].kind,expected[i].classes,expected[i].style],key);node.rect.forEach((n,k)=>assert(Math.abs(n-expected[i].rect[k])<=.05,'Internal geometry difference: '+key));});count++;
          }
          if(state==='detail')await close();
        }
        if(baseline&&theme==='light'){await go('home');await shot('toolbar-before-'+width);}
      }
    }
    assets.clear();for(const entry of saved)assets.set(...entry);await p.reload();
  }
  stage='states-and-keyboard';await p.setViewportSize({width:320,height:844});await language('zh-CN');await appearance('dark');await go('tasks');
  await p.locator('[data-task="school"] button').click();await p.keyboard.press('Tab');
  assert(await p.evaluate(()=>document.querySelector('dialog').contains(document.activeElement)));
  await p.locator('#assignee').selectOption('clara');await body.getByRole('button',{name:'调整分工',exact:true}).click();
  await body.getByRole('button',{name:'预览效果',exact:true}).click();assert(await p.getByText(copy['zh-CN'].notSaved,{exact:true}).isVisible());
  await p.locator('[data-task="school"] button').click();assert.equal(await p.locator('#assignee').inputValue(),'devon');await close();
  assert(await p.locator('[data-task="school"] button').evaluate(n=>document.activeElement===n));count++;
  for(const [id,action,status,name] of [['visit','标记完成','待完成','complete'],['finished-visit','恢复未完成','已完成','reopen']]){
    await p.locator('[data-task="'+id+'"] button').click();await body.getByRole('button',{name:action,exact:true}).click();await fits();await shot(name+'-dark-320');
    await body.getByRole('button',{name:'预览效果',exact:true}).click();assert(await p.locator('[data-task="'+id+'"] .tag').getByText(status,{exact:true}).isVisible());count++;
  }
  await p.locator('.design-tools summary').click();await p.getByRole('button',{name:'查看长标题样稿',exact:true}).click();await fits();await close();count++;
  await p.getByRole('button',{name:'查看控件样稿',exact:true}).click();await fits();assert(await p.locator('#sample-input').getAttribute('readonly')!==null);await shot('controls-dark-320');await close();count++;
  await p.getByRole('button',{name:'查看空状态样稿',exact:true}).click();await fits();await shot('empty-dark-320');await close();count++;
  await p.getByRole('button',{name:'查看结果未知样稿',exact:true}).click();await fits();await shot('unknown-dark-320');
  await body.getByRole('button',{name:'核对最近操作',exact:true}).click();assert(await body.getByText(copy['zh-CN'].checkBody,{exact:true}).isVisible());await close();count++;
  stage='system-and-quiet-offers';await appearance('system');await p.emulateMedia({colorScheme:'light'});assert.equal(await p.locator('html').getAttribute('data-theme'),'light');
  await p.emulateMedia({colorScheme:'dark'});await p.waitForFunction(()=>document.documentElement.dataset.theme==='dark');
  await appearance('light');await p.emulateMedia({colorScheme:'dark'});assert.equal(await p.locator('html').getAttribute('data-theme'),'light');count++;
  await p.locator('#more-label').click();await p.locator('#more-content button').filter({hasText:'优惠查询'}).click();
  assert(!await p.getByText(copy['zh-CN'].offerTitle,{exact:true}).isVisible());await p.getByRole('button',{name:'查看优惠排版样稿',exact:true}).click();
  assert(await p.getByText(copy['zh-CN'].offerTitle,{exact:true}).isVisible());await go('home');assert(!await p.getByText(copy['zh-CN'].offerTitle,{exact:true}).isVisible());count++;
  await p.reload();await p.locator('[data-task="visit"]').waitFor();assert.equal(await p.locator('html').getAttribute('data-theme'),'dark');
  assert.equal(await p.locator('html').getAttribute('lang'),'zh-CN');count++;
  assert.deepEqual(errors,[]);assert(requests.every(url=>new URL(url).origin===origin&&assets.has(new URL(url).pathname)));count++;
  console.log(count+' UX2 browser checks passed; three-asset loopback renderer, no CSP bypass, external network or database. Windows file opening remains a manual gate.');
})().catch(e=>{console.error('UX2 failed at '+stage+': '+e.message);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(server){server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}});
