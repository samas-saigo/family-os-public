'use strict';
// Approved fictional assets only. Offline injection bypasses CSP, not a Windows file:// certification.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {chromium}=require('playwright');
const i=require('../../prototypes/h0-workbench/i18n.js');
const root=path.resolve(__dirname,'../../prototypes/h0-workbench');
const capture=process.argv.includes('--screenshots');
if(capture&&!process.argv.includes('--synthetic-only'))throw Error('Explicit synthetic-only capture required');
if(crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'fixtures.js'))).digest('hex')!=='9d1e05da9b053408cadeb0b8e9240ac3bb405136d2bac4a8b03c8ea23004077a')throw Error('Unapproved fixture bytes');
let passed=0;
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.H0_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-crashpad-for-testing','--disable-background-networking']});
 try{
  const context=await browser.newContext({offline:true,bypassCSP:true});const requests=[],errors=[];
  await context.route('**/*',r=>{requests.push(r.request().url());r.abort();});const page=await context.newPage();page.setDefaultTimeout(8000);page.on('pageerror',e=>errors.push(e.message));
  const dialog=page.getByRole('dialog');
  async function load({width=1440,scheme='light',scripts=true}={}){
   await page.setViewportSize({width,height:width===1440?1000:844});await page.emulateMedia({colorScheme:scheme});await page.goto('about:blank');
   await page.setContent(fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script[^>]*src[^>]*><\/script>/g,'').replace(/<link[^>]*href[^>]*>/g,''));await page.addStyleTag({content:fs.readFileSync(path.join(root,'styles.css'),'utf8')});
   if(!scripts)return;
   for(const f of ['fixtures.js','translations.js','i18n.js','model.js','presentation.js'])await page.addScriptTag({content:fs.readFileSync(path.join(root,f),'utf8')});
   await page.evaluate(()=>{const Base=FamilyH0Model.Workbench;FamilyH0Model.Workbench=class extends Base{constructor(){super();globalThis.__appearanceModel=this;}};});
   await page.addScriptTag({content:fs.readFileSync(path.join(root,'app.js'),'utf8')});
  }
  const tr=async key=>i.t(await page.locator('html').getAttribute('lang'),key);
  const state=()=>page.evaluate(()=>JSON.stringify(globalThis.__appearanceModel.state));
  const mode=()=>page.locator('html').getAttribute('data-appearance');
  const theme=()=>page.locator('html').getAttribute('data-theme');
  const nav=async view=>{const b=page.locator(`button[data-view="${view}"]`);if(!await b.isVisible())await page.locator('#secondary-menu>summary').click();await b.click();};
  const click=async key=>dialog.getByRole('button',{name:await tr(key),exact:true}).click();
  const close=async()=>{if(await dialog.count())await page.keyboard.press('Escape');};
  const settings=async()=>{await close();if(!await page.locator('#demo-controls').isVisible())await page.locator('#secondary-menu>summary').click();await page.locator('#demo-controls').click();};
  const setMode=async value=>{await settings();await page.locator('#appearance-mode').selectOption(value);await close();};
  const language=async locale=>{await close();if(!await page.locator('#language').isVisible())await page.locator('#secondary-menu>summary').click();await page.locator('#language').selectOption(locale);};
  const inspect=async id=>{const locale=await page.locator('html').getAttribute('lang'),title=i.t(locale,`fixture.${id}.title`);await page.locator('main article').filter({has:page.getByRole('heading',{name:title,exact:true})}).getByRole('button').click();};
  async function system(scheme){await page.emulateMedia({colorScheme:scheme});await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));}
  const check=async(name,fn)=>{await fn();passed++;console.log(`PASS ${name}`);};
  async function legible(){
   const issues=await page.evaluate(()=>{
    const rgb=s=>{const x=s.match(/[\d.]+/g).map(Number);return [x[0],x[1],x[2],x.length>3?x[3]:1];};
    const mix=(a,b)=>a.slice(0,3).map((n,j)=>n*a[3]+b[j]*(1-a[3]));
    const light=c=>c.map(n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4;}).reduce((v,n,j)=>v+n*[.2126,.7152,.0722][j],0);
    const ratio=(a,b)=>{const [lo,hi]=[light(a),light(b)].sort((x,y)=>x-y);return(hi+.05)/(lo+.05);};
    const background=n=>{const chain=[];for(let e=n;e;e=e.parentElement)chain.unshift(e);return chain.reduce((bg,e)=>mix(rgb(getComputedStyle(e).backgroundColor),bg),[255,255,255]);};
    const active=document.querySelector('dialog[open]')||document.body,walk=document.createTreeWalker(active,NodeFilter.SHOW_TEXT),bad=[];
    while(walk.nextNode()){
     const n=walk.currentNode,e=n.parentElement;if(!n.textContent.trim()||!e||e.closest('.sr-only,script,style,option,noscript')||!e.checkVisibility({checkVisibilityCSS:true,checkOpacity:true}))continue;
     const r=document.createRange();r.selectNodeContents(n);if(![...r.getClientRects()].some(b=>b.width>0&&b.height>0))continue;
     const s=getComputedStyle(e),bg=background(e),fg=mix(rgb(s.color),bg),value=ratio(fg,bg);
     if(value<4.5-.01)bad.push({tag:e.tagName,id:e.id,class:e.className,foreground:s.color,background:bg,contrast:Math.round(value*100)/100});
    }
    const controls=[...active.querySelectorAll('button,select,summary')].filter(e=>e.checkVisibility({checkVisibilityCSS:true,checkOpacity:true})&&e.getClientRects().length);
    for(const e of controls){const b=e.getBoundingClientRect();if(b.height<44||e.scrollWidth>e.clientWidth+1||e.scrollHeight>e.clientHeight+1||getComputedStyle(e).textOverflow==='ellipsis')bad.push({control:e.tagName,id:e.id});}
    if(document.documentElement.scrollWidth>innerWidth)bad.push({overflow:true});return bad;
   });assert.deepEqual(issues,[]);
  }
  await check('CSS follows system appearance before scripts and supports native color-scheme',async()=>{
   for(const scheme of ['light','dark']){await load({scheme,scripts:false});const paper=await page.locator('html').evaluate(n=>getComputedStyle(n).getPropertyValue('--paper').trim());assert.equal(paper,scheme==='dark'?'#202327':'#ffffff');assert.ok((await page.locator('html').evaluate(n=>getComputedStyle(n).colorScheme)).includes(scheme));}
  });
  await check('default system mode follows live media changes without reload or business-state changes',async()=>{
   await load();const before=await state();assert.equal(await mode(),'system');assert.equal(await theme(),'light');
   await system('dark');assert.equal(await theme(),'dark');await legible();await system('light');assert.equal(await theme(),'light');assert.equal(await state(),before);
  });
  await check('manual overrides ignore system changes and returning to system resumes current and future changes',async()=>{
   await load();const before=await state();await setMode('dark');await system('light');assert.equal(await theme(),'dark');assert.equal(await mode(),'dark');
   await system('dark');await setMode('light');assert.equal(await theme(),'light');await system('light');await system('dark');assert.equal(await theme(),'light');
   await setMode('system');assert.equal(await theme(),'dark');await system('light');assert.equal(await theme(),'light');assert.equal(await state(),before);
  });
  await check('the only appearance control is inside Settings and does not leak into task or acceptance dialogs',async()=>{
   for(const width of [1440,390,320])for(const locale of i.LOCALES){
    await load({width});await language(locale);assert.equal(await page.locator('#appearance-mode').count(),0);await settings();
    const selector=page.getByRole('combobox',{name:i.t(locale,'appearance.title'),exact:true});assert.equal(await selector.count(),1);assert.deepEqual(await selector.locator('option').evaluateAll(ns=>ns.map(n=>n.value)),['system','light','dark']);
    await close();await nav('tasks');await inspect('task-school');assert.equal(await page.locator('#appearance-mode').count(),0);await close();await nav('pending');await inspect('workshop');await click('ui.accept.suggested.step');assert.equal(await page.locator('#appearance-mode').count(),0);await close();
   }
  });
  await check('system appearance changes preserve an open unsaved confirmation and Cancel still saves nothing',async()=>{
   await load();await nav('pending');const before=await state();await inspect('workshop');await click('ui.accept.suggested.step');const heading=await dialog.locator('h2').innerText();
   await system('dark');assert.equal(await dialog.getAttribute('data-mode'),'confirm');assert.equal(await dialog.locator('h2').innerText(),heading);assert.equal(await state(),before);await click('ui.cancel.no.change');assert.equal(await state(),before);
   await inspect('workshop');await click('ui.accept.suggested.step');await system('light');await click('ui.confirm.simulated.task.acceptance');await nav('tasks');
   const step=i.t('zh-CN','fixture.workshop.step');assert.equal(await page.locator('main article').filter({has:page.getByRole('heading',{name:step,exact:true})}).count(),1);
  });
  await check('appearance is tab-local across member and language views; invalid values cannot alter it',async()=>{
   await load();await setMode('dark');const before=await state();await language('en-US');await page.locator('#member').selectOption('julian');assert.equal(await theme(),'dark');assert.equal(await state(),before);
   await settings();await page.locator('#appearance-mode').evaluate(n=>{n.value='invalid';n.dispatchEvent(new Event('change',{bubbles:true}));});assert.equal(await mode(),'dark');assert.equal(await page.locator('#appearance-mode').inputValue(),'dark');await load({scheme:'light'});assert.equal(await mode(),'system');assert.equal(await theme(),'light');
  });
  await check('Reset cancellation preserves appearance; explicit reset returns to system',async()=>{
   await load({scheme:'dark'});await setMode('light');await page.locator('#reset').click();await click('ui.cancel.keep.demo.state');assert.equal(await mode(),'light');
   await page.locator('#reset').click();await click('ui.confirm.demo.reset');assert.equal(await mode(),'system');assert.equal(await theme(),'dark');
  });
  await check('appearance selection is keyboard reachable with visible focus in both themes and languages',async()=>{
   for(const width of [1440,390,320])for(const locale of i.LOCALES)for(const appearance of ['light','dark']){
    await load({width});await language(locale);await setMode(appearance);await settings();const select=page.locator('#appearance-mode');await page.keyboard.press('Tab');await select.focus();assert.ok(await select.evaluate(n=>n.matches(':focus-visible')));assert.ok(parseFloat(await select.evaluate(n=>getComputedStyle(n).outlineWidth))>=3);
    await page.keyboard.press('Home');await page.keyboard.press('ArrowDown');await page.keyboard.press('Tab');assert.equal(await mode(),'light');await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>document.activeElement.id),'view-heading');
   }
  });
  await check('both palettes keep text and controls legible across all views, dialogs, languages and narrow screens',async()=>{
   for(const width of [1440,390,320])for(const locale of i.LOCALES)for(const appearance of ['light','dark']){
    await load({width});await language(locale);await setMode(appearance);
    for(const view of ['home','tasks','pending','upcoming','security','information','offers']){await nav(view);await page.mouse.move(0,0);await legible();}
    await nav('pending');await inspect('workshop');await legible();await click('ui.accept.suggested.step');await legible();await close();await settings();await legible();await close();
   }
  });
  await check('no network, storage, private assets or runtime errors',async()=>{
   assert.deepEqual(requests,[]);assert.deepEqual(errors,[]);assert.ok(!/\b(?:localStorage|sessionStorage|indexedDB)\b/.test(fs.readFileSync(path.join(root,'app.js'),'utf8')));
  });
  if(capture){
   const output=path.resolve(__dirname,'../../docs/screenshots/appearance');fs.mkdirSync(output,{recursive:true});let count=0;
   const shot=async name=>{await page.mouse.move(0,0);await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(output,name+'.png')});count++;};
   for(const appearance of ['light','dark']){
    for(const width of [1440,390,320]){await load({width});await setMode(appearance);await nav('home');await shot(`home-${appearance}-${width}`);}
    await load({width:390});await language('en-US');await setMode(appearance);await nav('pending');await inspect('workshop');await click('ui.accept.suggested.step');await shot(`confirm-${appearance}-en-390`);
    await load();await setMode(appearance);await nav('home');await settings();await shot(`settings-${appearance}-1440`);
   }
   console.log(`Captured ${count} actual fictional appearance screenshots.`);
  }
  console.log(`${passed} appearance browser checks passed; offline harness, Windows file:// and OS settings remain manual gates.`);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
