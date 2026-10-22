'use strict';
// Optional offline browser checks. Local-content injection bypasses CSP; not a
// substitute for the manual Windows file-opening/CSP gate. No server or downloads.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const i=require('../../prototypes/h0-workbench/i18n.js');
const root=path.resolve(__dirname,'../../prototypes/h0-workbench');
let passed=0;
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.H0_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-crashpad-for-testing','--disable-background-networking']});
 try {
  const context=await browser.newContext({offline:true,bypassCSP:true,viewport:{width:1440,height:1000}});
  const requests=[],errors=[];
  await context.route('**/*',r=>{requests.push(r.request().url());r.abort();});
  const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));
  async function load(){
   await page.goto('about:blank');
   await page.setContent(fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script[^>]*src[^>]*><\/script>/g,'').replace(/<link[^>]*href[^>]*>/g,''),{waitUntil:'domcontentloaded'});
   await page.addStyleTag({content:fs.readFileSync(path.join(root,'styles.css'),'utf8')});
   for(const file of ['fixtures.js','translations.js','i18n.js','model.js','presentation.js','app.js'])await page.addScriptTag({content:fs.readFileSync(path.join(root,file),'utf8')});
  }
  const tr=(locale,key,values)=>i.t(locale,key,values);
  const nav=async(locale,key)=>{const b=page.locator('.sidebar').getByRole('button',{name:new RegExp(tr(locale,key))});if(!(await b.isVisible()))await page.locator('#secondary-menu>summary').click();await b.click();};
  const language=async(value)=>{if(!(await page.locator('#language').isVisible()))await page.locator('#secondary-menu>summary').click();await page.locator('#language').selectOption(value);};
  const dialog=page.getByRole('dialog');
  const card=(locale,id,field='title')=>page.locator('main article').filter({has:page.getByRole('heading',{name:tr(locale,`fixture.${id}.${field}`),exact:true})});
  const inspect=async(locale,id,field)=>card(locale,id,field).getByRole('button').click();
  const click=async(locale,key)=>dialog.getByRole('button',{name:tr(locale,key),exact:true}).click();
  async function fillSearch(value) { if(!(await page.locator('#search').isVisible()))await page.locator('#search-controls>summary').click();await page.locator('#search').fill(value); }
  async function check(name,fn){await fn();passed++;console.log(`PASS ${name}`);}
  async function noEnglish(){
   const text=await page.locator('body').innerText();
   const words=text.match(/[A-Za-z][A-Za-z0-9]*/g)||[];
   const allowed=new Set(['Samas','Family','OS','English','H1','JavaScript','Moss','Mug','Lantern','Trails','Old','Leaf','DEMO15','DEMO','WEEKEND','OLD','verify','mailbox','example','invalid','f']);
   assert.ok(words.every(w=>allowed.has(w)),`Untranslated Chinese UI: ${words.filter(w=>!allowed.has(w)).join(', ')}`);
  }
  await load();
  await check('fresh UI, accessible names and all seven views default to Chinese',async()=>{
   assert.equal(await page.locator('html').getAttribute('lang'),'zh-CN');assert.equal(await page.locator('#language').inputValue(),'zh-CN');
   assert.equal(await page.locator('#search').getAttribute('placeholder'),tr('zh-CN','chrome.placeholder'));
   for(const key of ['ui.home','ui.needs.action','ui.pending.confirmation','ui.upcoming','ui.security.review','ui.quiet.information','ui.offers']){await nav('zh-CN',key);await noEnglish();}
   assert.equal(await page.locator('main .coupon').count(),0);
  });
  await check('distinct peer preferences restore without changing shared counts',async()=>{
   await language('en-US');await nav('en-US','ui.home');const counts=await page.locator('.stat strong').allTextContents();
   await page.locator('#member').selectOption('julian');assert.equal(await page.locator('#language').inputValue(),'zh-CN');
   await page.locator('#member').selectOption('nora');assert.equal(await page.locator('#language').inputValue(),'en-US');assert.deepEqual(await page.locator('.stat strong').allTextContents(),counts);
   await language('zh-CN');
  });
  await check('Chinese keyword search selects permitted display text and not English aliases',async()=>{
   await nav('zh-CN','ui.needs.action');await fillSearch('出游包');assert.equal(await page.locator('main article').count(),1);
   await fillSearch('outing bag');assert.equal(await page.locator('main article').count(),0);
   await language('en-US');await fillSearch('outing bag');assert.equal(await page.locator('main article').count(),1);
   await language('zh-CN');
  });
  await check('details reopen in either language through the single global picker without a decision',async()=>{
   await nav('zh-CN','ui.pending.confirmation');await inspect('zh-CN','workshop');
   assert.equal(await dialog.locator('select').count(),0);await click('zh-CN','ui.back.to.workbench');await language('en-US');await inspect('en-US','workshop');
   assert.equal(await dialog.getByRole('heading').textContent(),tr('en-US','fixture.workshop.title'));
   await page.keyboard.press('Escape');await language('zh-CN');await inspect('zh-CN','workshop');await noEnglish();
   await click('zh-CN','ui.back.to.workbench');assert.ok((await page.locator('main').innerText()).includes('8 项'));
  });
  await check('cancel before the global language switch never accepts an unfinished confirmation',async()=>{
   await inspect('zh-CN','workshop');await click('zh-CN','ui.accept.suggested.step');await click('zh-CN','ui.cancel.no.change');await language('en-US');
   assert.equal(await dialog.count(),0);assert.equal(await page.locator('#feedback').textContent(),tr('en-US','locale.ready'));
   assert.ok((await page.locator('main').innerText()).includes('8 items'));
   await nav('en-US','ui.needs.action');assert.equal(await card('en-US','workshop','step').count(),0);
  });
  for(const locale of i.LOCALES){
   await check(`${locale}: review, acceptance and cancellation remain independent`,async()=>{
    await load();await language(locale);await nav(locale,'ui.pending.confirmation');await inspect(locale,'workshop');
    assert.equal(await dialog.getByRole('button',{name:tr(locale,'ui.record.simulated.review.only')}).count(),0);await click(locale,'ui.back.to.workbench');
    assert.equal(await card(locale,'workshop').count(),1);await inspect(locale,'workshop');await noEnglishIf(locale);
    await click(locale,'ui.accept.suggested.step');await click(locale,'ui.cancel.no.change');assert.equal(await card(locale,'workshop').count(),1);
    await inspect(locale,'workshop');await click(locale,'ui.accept.suggested.step');await click(locale,'ui.confirm.simulated.task.acceptance');
    await nav(locale,'ui.needs.action');assert.equal(await card(locale,'workshop','step').count(),1);
    await language(locale==='zh-CN'?'en-US':'zh-CN');
    const other=locale==='zh-CN'?'en-US':'zh-CN';assert.equal(await card(other,'workshop','step').count(),1);
   });
   await check(`${locale}: unknown safety, inert destinations and offers stay separate`,async()=>{
    await language(locale);await nav(locale,'ui.security.review');await inspect(locale,'login-risk');
    assert.equal(await dialog.getByRole('button',{name:tr(locale,'ui.accept.suggested.step')}).count(),0);assert.equal(await dialog.locator('a').count(),0);await noEnglishIf(locale);
    await click(locale,'ui.back.to.workbench');await nav(locale,'ui.offers');assert.equal(await page.locator('main .coupon').count(),0);
    await page.getByRole('button',{name:tr(locale,'ui.find.fictional.offers')}).click();assert.equal(await page.locator('main .coupon').count(),3);await noEnglishIf(locale);
    assert.ok(!(await page.locator('main').innerText()).includes(tr(locale,'fixture.promo-risk.title')));
   });
   await check(`${locale}: confirmed deferral preserves paginated backlog`,async()=>{
    await nav(locale,'ui.pending.confirmation');await inspect(locale,'visit');await click(locale,'ui.defer.question');await noEnglishIf(locale);await click(locale,'ui.confirm.deferral');
    assert.equal(await card(locale,'visit').count(),0);await page.locator('[data-bucket=later]').click();
    assert.ok((await card(locale,'visit').innerText()).includes(tr(locale,'ui.deferred.unresolved')));await page.locator('[data-bucket=active]').click();
    const titles=[];for(let n=0;n<3;n++){titles.push(...await page.locator('main article h3').allTextContents());if(n<2){const next=page.getByRole('button',{name:tr(locale,'ui.next'),exact:true});if(await next.isDisabled())break;await next.click();}}
    assert.equal(new Set(titles).size,6);assert.ok(!titles.includes(tr(locale,'fixture.expired-offer.title')));
   });
   await check(`${locale}: revocation removes translated source content while publication remains`,async()=>{
    await page.getByRole('button',{name:tr(locale,'ui.demo.sharing.controls'),exact:true}).click();await noEnglishIf(locale);
    await dialog.locator('.source-row').filter({hasText:tr(locale,'fixture.notices.title')}).getByRole('button',{name:tr(locale,'format.revokeButton',{member:tr(locale,'member.julian')}),exact:true}).click();
    await click(locale,'ui.confirm.demo.sharing.change');await page.locator('#member').selectOption('julian');await language(locale);
    await nav(locale,'ui.pending.confirmation');assert.ok(!(await page.locator('main').innerText()).includes(tr(locale,'fixture.visit.title')));
    assert.ok((await page.locator('main').innerText()).includes(locale==='zh-CN'?'3 项':'3 items'));
    await fillSearch(locale==='zh-CN'?'陶艺':'ceramics');assert.equal(await page.locator('main article').count(),0);
    await nav(locale,'ui.needs.action');await inspect(locale,'workshop','step');assert.ok(!(await dialog.innerText()).includes(tr(locale,'fixture.workshop.title')));await noEnglishIf(locale);await click(locale,'ui.back.to.workbench');
   });
  }
  async function noEnglishIf(locale){if(locale==='zh-CN')await noEnglish();}
  await check('localized tracking/history, keyboard Cancel and safe search markup',async()=>{
   await load();await nav('zh-CN','ui.needs.action');await inspect('zh-CN','task-school');await click('zh-CN','ui.simulate.completion');await noEnglish();await page.keyboard.press('Escape');assert.equal(await dialog.count(),0);
   await inspect('zh-CN','task-school');await click('zh-CN','ui.simulate.completion');await click('zh-CN','ui.confirm.simulated.tracking.change');
   await page.getByRole('button',{name:tr('zh-CN','ui.show.simulated.completed.steps')}).click();await inspect('zh-CN','task-school');await noEnglish();await dialog.locator('.context-details>summary').click();assert.ok((await dialog.innerText()).includes(tr('zh-CN','ui.simulated.history')));await click('zh-CN','ui.back.to.workbench');
   await fillSearch('<img src=x onerror=alert(1)>');assert.equal(await page.locator('main img').count(),0);await fillSearch('');
  });
  await check('localized evidence-version warning and blocked acceptance preserve history',async()=>{
   await nav('zh-CN','ui.pending.confirmation');await inspect('zh-CN','workshop');await click('zh-CN','ui.accept.suggested.step');await click('zh-CN','ui.confirm.simulated.task.acceptance');
   await page.getByRole('button',{name:tr('zh-CN','ui.demo.sharing.controls'),exact:true}).click();await click('zh-CN','ui.change.the.workshop.evidence.sample');await click('zh-CN','ui.confirm.sample.evidence.change');
   await nav('zh-CN','ui.needs.action');await inspect('zh-CN','workshop','step');await noEnglish();assert.ok((await dialog.innerText()).includes('相关信息已更新，请重新确认'));await click('zh-CN','ui.back.to.workbench');
   await nav('zh-CN','ui.pending.confirmation');await inspect('zh-CN','workshop');assert.equal(await dialog.getByRole('button',{name:tr('zh-CN','ui.accept.suggested.step')}).count(),0);await click('zh-CN','ui.back.to.workbench');
  });
  await check('both languages fit desktop and narrow widths with keyboard-reachable navigation',async()=>{
   await load();const dir=process.env.H1_SCREENSHOT_DIR;if(dir)fs.mkdirSync(dir,{recursive:true});
   for(const locale of i.LOCALES){await language(locale);
    for(const width of [1440,390,320]){await page.setViewportSize({width,height:900});
     for(const key of ['ui.home','ui.pending.confirmation','ui.security.review','ui.offers']){await nav(locale,key);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),`${locale} ${width} ${key}`);}
     await nav(locale,'ui.pending.confirmation');await inspect(locale,'workshop');await click(locale,'ui.accept.suggested.step');
     assert.ok(await dialog.evaluate(node=>node.scrollWidth<=node.clientWidth));await page.keyboard.press('Tab');assert.ok(await page.evaluate(()=>['BUTTON','SELECT'].includes(document.activeElement.tagName)));await page.keyboard.press('Escape');
     await nav(locale,'ui.home');if(dir&&width!==320)await page.screenshot({path:path.join(dir,`h1-${locale}-${width}.png`),fullPage:true});
    }
   }
  });
  await check('no network request/runtime errors/storage and no active external links',async()=>{
   assert.deepEqual(requests,[]);assert.deepEqual(errors,[]);assert.deepEqual(await page.locator('a').evaluateAll(ns=>ns.map(n=>n.getAttribute('href'))),['#main']);
  });
  console.log(`${passed} bilingual browser checks passed (local-content/CSP-bypass harness, no file:// claim).`);
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
