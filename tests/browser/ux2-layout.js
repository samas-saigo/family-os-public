'use strict';
// Disposable visual renderer only; no account, API, storage or database.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http');
if(!process.argv.includes('--synthetic-only'))throw Error('Explicit synthetic opt-in required');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..'),ui=path.join(root,'prototypes/ux2-design-preview');
const images=path.join(root,'docs/screenshots/ux2-calm-premium'),capture=process.argv.includes('--screenshots');
const before=process.argv.includes('--capture-before');
const {copy}=require(path.join(ui,'preview.js'));let browser,server,count=0,stage='startup';
(async()=>{
  const assets=new Map([['/','index.html'],['/styles.css','styles.css'],['/preview.js','preview.js']].map(([url,file])=>[url,fs.readFileSync(path.join(ui,file))]));
  server=http.createServer((req,res)=>{if(req.method!=='GET'||!assets.has(req.url)){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',req.url.endsWith('.css')?'text/css':req.url.endsWith('.js')?'text/javascript':'text/html; charset=utf-8');res.end(assets.get(req.url));});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;
  browser=await chromium.launch({executablePath:process.env.UX2_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const context=await browser.newContext({viewport:{width:1828,height:1000},colorScheme:'light'}),p=await context.newPage(),errors=[],requests=[];
  p.setDefaultTimeout(8000);p.on('pageerror',e=>errors.push(e.name));p.on('request',r=>requests.push(r.url()));
  await context.route('**/*',route=>new URL(route.request().url()).origin===origin&&assets.has(new URL(route.request().url()).pathname)?route.continue():route.abort());
  await p.goto(origin);let locale='zh-CN';
  async function go(view){
    if(view==='a1'||view==='a2'){await go('home');await p.locator('[data-design-choice="'+view+'"]').click();return;}
    if(['home','tasks','pending','calendar','security'].includes(view))await p.locator('#navigation button[data-view="'+view+'"]').click();
    else if(await p.locator('#secondary').isVisible())await p.locator('#secondary button').filter({hasText:copy[locale][view]}).click();
    else{await p.locator('#more-label').click();await p.locator('#more-content button').filter({hasText:copy[locale][view]}).click();}
  }
  async function language(value){
    await p.waitForFunction(()=>Boolean(document.querySelector('#language').closest(matchMedia('(max-width:730px)').matches?'#more-content':'#desktop-language')));
    if(!await p.locator('#language').isVisible())await p.locator('#more-label').click();
    await p.locator('#language').selectOption(value);locale=value;
  }
  async function shot(name){if(capture){await p.mouse.move(0,0);await p.screenshot({path:path.join(images,name+'.png')});}}
  async function geometry(){return p.evaluate(()=>{
    const rect=n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};};
    const bar=document.querySelector('.topbar');return {workspace:rect(document.querySelector('.workspace')),bar:rect(bar),main:rect(document.querySelector('main')),gap:parseFloat(getComputedStyle(bar).marginBottom)};
  });}
  if(before){
    assert(capture,'Before mode only records baseline evidence; use --screenshots');
    for(const view of ['calendar','security']){await go('a1');await go(view);console.log('Before '+view+': '+JSON.stringify(await geometry()));await shot('layout-before-'+view+'-1828');}
    console.log('2 baseline captures only; this mode does not claim regression success.');return;
  }
  const origins=new Map();
  for(const lang of ['zh-CN','en-US'])for(const theme of ['light','dark'])for(const width of [1828,1440,1152,960,390,320])for(const height of (width>730?[1000,1600]:[844,1200])){
    await p.setViewportSize({width,height});await language(lang);await go('settings');await p.locator('#appearance').selectOption(theme);
    // Always traverse Home first, then the short Calendar/Security pages.
    for(const view of ['a1','calendar','security','a2','tasks','pending','offers','settings']){
      stage=[lang,theme,width,height,view].join('/');await go(view);const g=await geometry();
      assert(Math.abs(g.workspace.y)<.05,'Workspace must begin at viewport top: '+JSON.stringify(g));
      assert(Math.abs(g.bar.y)<.05,'Toolbar must never sink with short content');
      assert(Math.abs(g.main.y-(g.bar.y+g.bar.height+g.gap))<.05,'Main begins directly after the shared toolbar gap');
      const key=[lang,theme,width].join('/'),origin=[g.bar.x,g.bar.y,g.bar.width,g.bar.height,g.main.x,g.main.y,g.main.width];
      if(origins.has(key))assert.deepEqual(origin,origins.get(key),'Page/height must not change shared origins');else origins.set(key,origin);
      assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow');
      const bad=await p.evaluate(()=>[...document.querySelectorAll('button,select,summary')].filter(n=>{const r=n.getBoundingClientRect();return r.width&&r.height&&(n.scrollWidth>n.clientWidth+1||r.height<44||r.x<-.5||r.right>innerWidth+.5);}).map(n=>n.textContent.trim()));
      assert.deepEqual(bad,[]);
      if(width<731){
        const nav=await p.locator('#navigation').boundingBox();
        if(view==='a1'||view==='a2'){const first=await p.locator('[data-task="visit"] button').boundingBox();assert(first.y+first.height<nav.y,'First action must remain above bottom navigation');}
        const controls=p.locator('#main button:visible,#main select:visible');if(await controls.count()){
          await p.evaluate(()=>scrollTo(0,document.documentElement.scrollHeight));const last=await controls.last().boundingBox(),fixed=await p.locator('#navigation').boundingBox();
          assert(last.y+last.height<=fixed.y+.5,'Final visible control must be reachable above bottom navigation: '+JSON.stringify({last,fixed,text:await controls.last().textContent()}));await p.evaluate(()=>scrollTo(0,0));
        }
      }
      if(lang==='zh-CN'&&theme==='light'){
        if(width===1828&&height===1000&&['calendar','security'].includes(view))await shot('layout-after-'+view+'-1828');
        if(width===1440&&height===1000&&['a1','tasks'].includes(view))await shot('layout-after-'+view+'-1440');
        if(width===390&&height===844&&['a1','calendar','security','tasks'].includes(view))await shot('layout-after-'+view+'-390');
        if(width===320&&height===844&&view==='a1')await shot('layout-after-a1-320');
      }
      count++;
    }
  }
  assert.deepEqual(errors,[]);assert(requests.every(url=>new URL(url).origin===origin&&assets.has(new URL(url).pathname)));
  console.log(count+' UX2 page/height geometry cases passed; 8 views, 6 widths, 2 heights, 2 languages, 2 themes. No network/API/database; Windows direct-file review remains manual.');
})().catch(e=>{console.error('UX2 layout failed at '+stage+': '+e.message);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(server){server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}});
