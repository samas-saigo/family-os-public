'use strict';
// Optional developer capture: approved fixed fiction, offline browser, no server.
// CSP bypass only injects files. Windows direct-file/CSP/real zoom remains a user gate.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {chromium}=require('playwright');
const args=process.argv.slice(2);
if(args[0]!=='--synthetic-only')throw Error('Explicit synthetic-only capture required');
const baseline=args[1]==='--baseline', controlsReview=args.includes('--controls-review'), dashboardReview=args.includes('--dashboard-review'), brandReview=args.includes('--brand-review'), wordmarkReview=args.includes('--wordmark-review'), spacingReview=args.includes('--spacing-review'), singleEntryReview=args.includes('--single-entry-review');
const root=baseline?path.resolve(args[2]):path.resolve(__dirname,'../../prototypes/h0-workbench');
const out=path.resolve(__dirname,singleEntryReview?'../../docs/screenshots/ux1-single-entry':spacingReview?'../../docs/screenshots/ux1-spacing':wordmarkReview?'../../docs/screenshots/ux1-wordmark':brandReview?'../../docs/screenshots/ux1-brand':dashboardReview?'../../docs/screenshots/ux1-dashboard':controlsReview?'../../docs/screenshots/ux1-controls':'../../docs/screenshots/ux1-polish');
if(crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'fixtures.js'))).digest('hex')!=='9d1e05da9b053408cadeb0b8e9240ac3bb405136d2bac4a8b03c8ea23004077a')throw Error('Unapproved fixture bytes');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.H0_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-crashpad-for-testing','--disable-background-networking']});
 try{
  const context=await browser.newContext({offline:true,bypassCSP:true});await context.route('**/*',r=>r.abort());
  const page=await context.newPage();let captures=0;const errors=[];page.on('pageerror',e=>errors.push(e.message));fs.mkdirSync(out,{recursive:true});
  async function load(width=390){await page.setViewportSize({width,height:width>1000?1000:844});await page.goto('about:blank');await page.setContent(fs.readFileSync(path.join(root,'index.html'),'utf8').replace(/<script[^>]*src[^>]*><\/script>/g,'').replace(/<link[^>]*href[^>]*>/g,''));await page.addStyleTag({content:fs.readFileSync(path.join(root,'styles.css'),'utf8')});for(const file of ['fixtures.js','translations.js','i18n.js','model.js','presentation.js','app.js'])await page.addScriptTag({content:fs.readFileSync(path.join(root,file),'utf8')});}
  const nav=key=>page.locator(`[data-view=${key}]`).click();
  const inspect=async id=>{const title=await page.evaluate(id=>FamilyH1I18n.t('zh-CN',`fixture.${id}.title`),id);await page.locator('main article').filter({has:page.getByRole('heading',{name:title,exact:true})}).getByRole('button').click();};
  const click=async key=>{const name=await page.evaluate(key=>FamilyH1I18n.t('zh-CN',key),key);await page.getByRole('dialog').getByRole('button',{name,exact:true}).click();};
  const shot=async name=>{if(brandReview&&!['home-desktop','home-390','task-detail-390','task-confirm-320'].includes(name))return;if(dashboardReview&&!['home-390','home-320','home-desktop'].includes(name))return;if(controlsReview&&!['home-390','home-320','home-desktop','pending-390','tasks-desktop','accept-320'].includes(name))return;captures++;await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(out,`${baseline?'before':'after'}-${name}.png`)});};
  const settings=async()=>{if(!await page.locator('#demo-controls').isVisible())await page.locator('#secondary-menu>summary').click();await page.locator('#demo-controls').click();};
  if(singleEntryReview){
   const language=async locale=>{if(!await page.locator('#language').isVisible())await page.locator('#secondary-menu>summary').click();await page.locator('#language').selectOption(locale);};
   const inspectLocalized=async(locale,id)=>{const title=await page.evaluate(({locale,id})=>FamilyH1I18n.t(locale,`fixture.${id}.title`),{locale,id});await page.locator('main article').filter({has:page.getByRole('heading',{name:title,exact:true})}).getByRole('button').click();};
   for(const locale of ['zh-CN','en-US']){
    const label=locale==='zh-CN'?'zh':'en';
    await load(1440);await language(locale);await nav('tasks');await inspectLocalized(locale,'task-school');await shot(`task-detail-${label}-desktop`);
    await load(390);await language(locale);await nav('pending');await inspectLocalized(locale,'workshop');const accept=await page.evaluate(locale=>FamilyH1I18n.t(locale,'ui.accept.suggested.step'),locale);await page.getByRole('dialog').getByRole('button',{name:accept,exact:true}).click();await shot(`accept-${label}-390`);
    await load(320);await language(locale);await page.locator('#secondary-menu>summary').click();await shot(`global-menu-${label}-320`);
   }
   if(errors.length)throw Error(errors.join(';'));console.log(`Captured ${captures} ${baseline?'baseline':'updated'} fictional bilingual single-entry screenshots; no real data or network.`);return;
  }
  if(spacingReview){
   await load(1440);await shot('home-desktop');await page.locator('#search-controls>summary').click();await shot('filters-desktop');await nav('tasks');await page.locator('#search-controls>summary').click();await shot('tasks-desktop');
   await load(390);await shot('home-390');await load(320);await shot('home-320');
   if(errors.length)throw Error(errors.join(';'));console.log(`Captured ${captures} ${baseline?'baseline':'updated'} fictional spacing screenshots; no real data or network.`);return;
  }
  if(wordmarkReview){
   await load(1440);await shot('home-desktop');await nav('tasks');await shot('tasks-desktop');
   await load(390);await shot('home-390');await nav('tasks');await shot('tasks-390');
   await load(320);await nav('tasks');await shot('tasks-320');
   if(errors.length)throw Error(errors.join(';'));console.log(`Captured ${captures} ${baseline?'baseline':'updated'} fictional wordmark/toggle screenshots; no real data or network.`);return;
  }
  if(brandReview){
   await load(1440);await shot('home-desktop');await load(390);await shot('home-390');
   await nav('tasks');await inspect('task-school');await shot('task-detail-390');
   await load(320);await nav('tasks');await inspect('task-school');await click('ui.simulate.completion');await shot('task-confirm-320');
   if(errors.length)throw Error(errors.join(';'));console.log(`Captured ${captures} ${baseline?'baseline':'updated'} fictional brand/action screenshots; no real data or network.`);return;
  }
  await load();await shot('home-390');
  await load(320);if(controlsReview||dashboardReview)await shot('home-320');await nav('pending');await shot('pending-320');await inspect('workshop');await click('ui.accept.suggested.step');await shot('accept-320');
  await load();await settings();await shot('settings-390');
  if(!baseline||controlsReview||dashboardReview){
   await load(1440);await shot('home-desktop');await nav('tasks');await shot('tasks-desktop');await nav('upcoming');await shot('calendar-desktop');
   await load();await nav('pending');await shot('pending-390');await inspect('visit');await click('ui.defer.question');await click('ui.confirm.deferral');await page.locator('[data-bucket=later]').click();await shot('later-390');
   await page.locator('[data-bucket=active]').click();await inspect('workshop');await click('pending.archive');await shot('archive-390');await click('pending.archive.save');await page.locator('[data-bucket=archived]').click();await shot('archived-390');
   await load();await nav('security');await shot('security-390');
   if(!await page.locator('[data-view=offers]').isVisible())await page.locator('#secondary-menu>summary').click();await nav('offers');await shot('offers-gate-390');const label=await page.evaluate(()=>FamilyH1I18n.t('zh-CN','ui.find.fictional.offers'));await page.getByRole('button',{name:label,exact:true}).click();await shot('offers-390');
   await load(320);await settings();await page.getByRole('dialog').locator('.source-row').first().getByRole('button').click();await shot('revoke-320');
   await load(390);await page.locator('#secondary-menu>summary').click();await page.locator('#language').selectOption('en-US');await nav('pending');await shot('pending-en-390');
  }
  if(errors.length)throw Error(errors.join(';'));console.log(`Captured ${captures} ${baseline?'baseline':'updated'} fictional screenshots; no real data or network.`);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
