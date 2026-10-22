'use strict';
// Optional browser probe: generated fiction only, no listener or browser downloads.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require('playwright');
const dir = path.resolve(process.argv[2]);
let passed = 0;
(async () => {
  const browser = await chromium.launch({executablePath: process.env.H0_CHROMIUM || '/usr/bin/chromium',
    headless: true, args: ['--no-sandbox', '--disable-crashpad-for-testing', '--disable-background-networking']});
  try {
    const context = await browser.newContext({offline: true, bypassCSP: true, viewport: {width: 1440, height: 1000}});
    const requests = [], errors = [];
    await context.route('**/*', route => {requests.push(route.request().url()); route.abort();});
    // Direct file opening is attempted separately. Injection bypasses CSP and does
    // not prove Windows file:// behavior or the real local-file CSP boundary.
    let direct = 'not attempted';
    const probeContext = await browser.newContext({offline: true});
    const probe = await probeContext.newPage();
    try {await probe.goto('file://'+path.join(dir, 'index.html'), {timeout: 5000}); direct = 'opened';}
    catch (error) {direct = error.message.includes('ERR_BLOCKED_BY_ADMINISTRATOR') ? 'blocked by environment policy' : 'not verified';}
    finally {await probeContext.close();}
    const page = await context.newPage(); page.setDefaultTimeout(10000);
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent(fs.readFileSync(path.join(dir, 'index.html'), 'utf8')
      .replace(/<script[^>]*src[^>]*><\/script>/g, '').replace(/<link[^>]*href[^>]*>/g, ''));
    await page.addStyleTag({content: fs.readFileSync(path.join(dir, 'styles.css'), 'utf8')});
    for (const file of ['h2-translations.js', 'i18n.js', 'snapshot.js', 'presentation.js', 'app.js'])
      await page.addScriptTag({content: fs.readFileSync(path.join(dir, file), 'utf8')});
    async function check(name, fn) {await fn(); passed++; console.log('PASS '+name);}
    const total = async () => Number(await page.locator('.stat strong').first().textContent());
    const nav = async index => page.locator('#navigation button').nth(index).click();
    await check('Chinese-first actual backend content and historical warning', async () => {
      assert.equal(await page.locator('html').getAttribute('lang'), 'zh-CN');
      assert.equal(await total(), 5); assert.equal(await page.locator('main article').count(), 2);
      assert.match(await page.locator('#warning').innerText(), /不是登录.*旧快照不代表当前权限/);
    });
    await check('both adults shared totals and private record isolation across pages', async () => {
      await page.getByRole('button', {name: '下一获准后端页', exact: true}).click();
      await page.getByRole('button', {name: '下一获准后端页', exact: true}).click();
      assert.match(await page.locator('main').innerText(), /h2-iris-private/);
      await page.locator('#peer').selectOption('soren'); assert.equal(await total(), 4);
      for (let n=0;n<2;n++) {assert.ok(!(await page.locator('main').innerText()).includes('h2-iris-private'));
        if (!n) await page.getByRole('button', {name: '下一获准后端页', exact: true}).click();}
    });
    await check('language changes preserve returned records and numbers', async () => {
      await page.locator('#language').selectOption('en-US'); assert.equal(await total(), 4);
      assert.equal(await page.locator('main h1').textContent(), 'Authorized information');
      assert.match(await page.locator('#warning').innerText(), /not login or a privacy boundary/);
      await page.locator('#language').selectOption('zh-CN');
    });
    await check('fresh revocation scenarios and independent shared steps', async () => {
      await page.locator('#peer').selectOption('iris'); await page.locator('#phase').selectOption('source-revoked');
      assert.equal(await total(), 3); assert.ok(!(await page.locator('main').innerText()).includes('h2-common-a'));
      await nav(2); assert.equal(await total(), 1); assert.match(await page.locator('main').innerText(), /不是已接受待办/);
      await page.locator('#phase').selectOption('publication-revoked'); assert.equal(await total(), 0);
      assert.equal(await page.locator('main article').count(), 0);
    });
    await check('unknown safety stays unknown; scope is independent', async () => {
      await page.locator('#phase').selectOption('initial'); await nav(1);
      assert.match(await page.locator('main').innerText(), /不能视为安全/);
      assert.match(await page.locator('main').innerText(), /不是检测结果/);
      await page.locator('#phase').selectOption('observation-only'); assert.equal(await total(), 0);
      await nav(0); assert.equal(await total(), 3);
    });
    await check('read-only controls never offer acceptance, login or mailbox writes', async () => {
      assert.equal(await page.locator('form, input, dialog, iframe').count(), 0);
      assert.equal(await page.locator('main article button, main article a').count(), 0);
      for (const locale of ['zh-CN', 'en-US']) {await page.locator('#language').selectOption(locale);
        for (const width of [1440, 390, 320]) {await page.setViewportSize({width, height: 900});
          for (let lane=0;lane<3;lane++) {await nav(lane);assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));}}
      }
    });
    await check('malformed response rejects without partial row output', async () => {
      await page.evaluate(() => {globalThis.FamilyH2Snapshot.scenarios[0].peers[0].pages[0].observations.items[0].source_id='<img src=x onerror=alert(1)>';});
      await page.locator('#phase').selectOption('initial');
      assert.equal(await page.locator('main article, main img, main script').count(), 0);
      assert.match(await page.locator('main').innerText(), /unavailable/);
    });
    assert.deepEqual(requests, []); assert.deepEqual(errors, []);
    console.log(JSON.stringify({passed, networkRequests: requests.length, browserErrors: errors.length,
      directFileAttempt: direct, WindowsManualGate: 'NOT VERIFIED; content injection bypassed CSP'}));
  } finally {await browser.close();}
})().catch(error => {console.error('H2 fictional browser check failed: '+error.name+
  ' at test line '+(/h2-interactions.js:(\d+)/.exec(error.stack || '') || [,'unknown'])[1]); process.exitCode = 1;});
