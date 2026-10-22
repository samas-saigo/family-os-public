'use strict';
// Optional developer browser checks. No server: local content + every request aborted.
// This harness bypasses CSP only to inject those files into about:blank; it does not
// verify file:// browser policy or CSP enforcement. The static tests check the CSP.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '../../prototypes/h0-workbench');
const capture = process.env.H0_SCREENSHOT_DIR;
let passed = 0;
(async () => {
  const browser = await chromium.launch({executablePath: process.env.H0_CHROMIUM || '/usr/bin/chromium', headless: true,
    args: ['--no-sandbox', '--disable-crashpad-for-testing', '--disable-background-networking']});
  try {
    const context = await browser.newContext({offline: true, bypassCSP: true, viewport: {width: 1440, height: 1000}});
    const requests = [], errors = [];
    await context.route('**/*', request => { requests.push(request.request().url()); request.abort(); });
    const page = await context.newPage(); page.setDefaultTimeout(10000); page.on('pageerror', e => errors.push(e.message));
    async function load() {
      const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8')
        .replace(/<script[^>]*src[^>]*><\/script>/g, '').replace(/<link[^>]*href[^>]*>/g, '');
      await page.goto('about:blank');
      await page.setContent(html, {waitUntil: 'domcontentloaded'});
      await page.addStyleTag({content: fs.readFileSync(path.join(root, 'styles.css'), 'utf8')});
      for (const file of ['fixtures.js', 'translations.js', 'i18n.js', 'model.js', 'presentation.js', 'app.js']) await page.addScriptTag({content: fs.readFileSync(path.join(root, file), 'utf8')});
    }
  async function fillSearch(value) { if(!(await page.locator('#search').isVisible()))await page.locator('#search-controls>summary').click();await page.locator('#search').fill(value); }
    async function check(name, fn) { await fn(); passed++; console.log(`PASS ${name}`); }
    const nav = async name => {const b=page.locator('.sidebar').getByRole('button', {name:new RegExp(name)});if(!(await b.isVisible()))await page.locator('#secondary-menu>summary').click();await b.click();};
    const card = title => page.locator('main article').filter({has: page.getByRole('heading', {name: title, exact: true})});
    const dialog = page.getByRole('dialog');
    const close = () => dialog.getByRole('button', {name: 'Back to the app', exact: true}).click();
    const inspect = title => card(title).getByRole('button').click();
    await load();
    // H0 English regressions now explicitly select each peer's in-memory locale.
    await page.locator('#language').selectOption('en-US');
    await page.locator('#member').selectOption('julian');
    await page.locator('#language').selectOption('en-US');
    await page.locator('#member').selectOption('nora');
    await check('seven views navigate and offer results need explicit intent', async () => {
      assert.equal(await page.locator('#navigation button').count(), 7);
      for (const name of ['Tasks', 'Pending', 'Calendar', 'Security', 'Information', 'Offers']) {await nav(name); assert.equal(await page.locator('h1').textContent(), name);}
      assert.equal(await page.locator('main .coupon').count(), 0);
      await page.getByRole('button', {name: 'Find fictional offers'}).click();
      assert.equal(await page.locator('main .coupon').count(), 3);
      assert.ok(!(await page.locator('main').textContent()).includes('Promotion with an unverified destination'));
    });
    await check('pending pagination retains all questions and excludes advertising', async () => {
      await nav('Pending'); const titles = [];
      for (let n = 0; n < 3; n++) {
        titles.push(...await page.locator('main article h3').allTextContents());
        if (n < 2) await page.getByRole('button', {name: 'Next', exact: true}).click();
      }
      assert.equal(new Set(titles).size, 8); assert.ok(!titles.some(t => /offer|promotion/i.test(t)));
      assert.ok(titles.includes('School timing question awaiting verification'));
    });
    await check('cancel and Escape preserve the unaccepted suggestion', async () => {
      await nav('Pending'); await inspect('School workshop preference requested');
      await dialog.getByRole('button', {name: 'Add to household tasks', exact: true}).click();
      await dialog.getByRole('button', {name: 'Cancel — no change', exact: true}).click();
      assert.ok((await page.locator('main').textContent()).includes('8 items'));
      await inspect('School workshop preference requested'); await dialog.getByRole('button', {name: 'Add to household tasks', exact: true}).click();
      await page.keyboard.press('Escape'); assert.equal(await dialog.count(), 0);
      assert.ok((await page.locator('main').textContent()).includes('8 items'));
    });
    await check('review and task acceptance require separate confirmations', async () => {
      await inspect('School workshop preference requested');
      assert.equal(await dialog.getByRole('button', {name: 'Record simulated review only', exact: true}).count(), 0);
      await close();
      assert.ok((await page.locator('main').textContent()).includes('8 items'));
      await inspect('School workshop preference requested');
      assert.ok(!(await dialog.textContent()).includes('Review: Unreviewed'));
      await dialog.getByRole('button', {name: 'Add to household tasks', exact: true}).click();
      await dialog.getByRole('button', {name: 'Confirm acceptance', exact: true}).click();
      assert.ok((await page.locator('main').textContent()).includes('7 items'));
      await nav('Tasks'); assert.equal(await card('Send a workshop preference').count(), 1);
    });
    await check('tracking status is independently confirmed and shared between peers', async () => {
      await inspect('Send a workshop preference'); await dialog.getByRole('button', {name: 'Mark complete', exact: true}).click();
      await dialog.getByRole('button', {name: 'Confirm status', exact: true}).click();
      assert.equal(await card('Send a workshop preference').count(), 0);
      await page.getByRole('button', {name: 'Show completed tasks'}).click();
      assert.ok((await card('Send a workshop preference').textContent()).includes('Completed'));
      await page.locator('#member').selectOption('julian'); await nav('Tasks');
      await page.getByRole('button', {name: 'Show completed tasks'}).click();
      assert.ok((await card('Send a workshop preference').textContent()).includes('Completed'));
    });
    await check('deferred uncertainty remains discoverable and creates no task', async () => {
      await nav('Pending'); await inspect('Repair visit access arrangements');
      assert.equal(await dialog.getByRole('button', {name: 'Add to household tasks', exact: true}).count(), 0);
      await dialog.getByRole('button', {name: 'Handle later', exact: true}).click();
      await dialog.getByRole('button', {name: 'Confirm later', exact: true}).click();
      assert.equal(await card('Repair visit access arrangements').count(), 0);
      await page.locator('[data-bucket=later]').click();
      assert.ok((await card('Repair visit access arrangements').textContent()).includes('Deferred'));
    });
    await check('security inspection and annotations cannot clear danger or accept tasks', async () => {
      await nav('Security'); await inspect('Unverified mailbox sign-in request');
      assert.equal(await dialog.getByRole('button', {name: 'Add to household tasks', exact: true}).count(), 0);
      assert.equal(await dialog.locator('a').count(), 0);
      assert.ok((await dialog.locator('code').textContent()).includes('INERT TEXT'));
      assert.equal(await dialog.getByRole('button', {name: 'Record simulated review only', exact: true}).count(), 0);
      await close();
      await inspect('Unverified mailbox sign-in request'); assert.ok((await dialog.textContent()).includes('High risk')); await close();
    });
    await check('search treats user input as text, not HTML', async () => {
      await fillSearch('<img src=x onerror=alert(1)>');
      assert.equal(await page.locator('main img').count(), 0);
      assert.ok((await page.locator('main').textContent()).includes('<img src=x onerror=alert(1)>'));
      await fillSearch('');
    });
    await check('private detail does not survive persona switch', async () => {
      await page.locator('#member').selectOption('nora'); await nav('Pending');
      await fillSearch('ceramics');
      await inspect('Nora’s private ceramics session choice');
      // Browser persona selector is outside the native modal; use a synthetic change
      // event to exercise the same handler used by the enabled selector when closed.
      await page.locator('#member').evaluate(node => {node.value = 'julian'; node.dispatchEvent(new Event('change'));});
      assert.equal(await dialog.count(), 0);
      assert.ok(!(await page.locator('body').textContent()).includes('Nora’s private ceramics session choice'));
    });
    await check('revocation hides source items/counts while published task remains neutral', async () => {
      await page.locator('#member').selectOption('nora');
      await page.getByRole('button', {name: 'Settings & Privacy', exact: true}).click();
      await dialog.locator('.source-row').filter({hasText: 'Linden household notices'}).getByRole('button', {name: 'Revoke Julian’s demo read access', exact: true}).click();
      await dialog.getByRole('button', {name: 'Confirm permissions', exact: true}).click();
      await page.locator('#member').selectOption('julian'); await nav('Pending');
      assert.ok(!(await page.locator('main').textContent()).includes('Repair visit access arrangements'));
      assert.ok((await page.locator('main').textContent()).includes('3 items'));
      await nav('Tasks'); await page.getByRole('button', {name: 'Show completed tasks'}).click(); await inspect('Send a workshop preference');
      assert.ok(!(await dialog.textContent()).includes('School workshop preference requested'));
      assert.ok((await dialog.textContent()).includes('separate sharing permission')); await close();
      await fillSearch('School workshop preference requested');
      assert.equal(await page.locator('main article').count(), 0);
    });
    await check('reset restores fixture state, leaving no browser persistence', async () => {
      await page.getByRole('button', {name: 'Reset demo', exact: true}).click();
      await dialog.getByRole('button', {name: 'Confirm demo reset', exact: true}).click();
      assert.equal(await page.locator('#member').inputValue(), 'nora'); await page.locator('#language').selectOption('en-US');
      await nav('Tasks'); assert.equal(await card('Send a workshop preference').count(), 0);
      await page.locator('#language').selectOption('en-US'); await nav('Home');
    });
    await check('desktop and mobile fit without horizontal page overflow', async () => {
      if (capture) {fs.mkdirSync(capture, {recursive: true}); await page.screenshot({path: path.join(capture, 'h0-desktop.png'), fullPage: true});}
      for (const width of [390, 320]) {
        await page.setViewportSize({width, height: 844});
        for (const name of ['Home', 'Pending', 'Security', 'Offers']) {
          await nav(name); assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `${width} ${name}`);
        }
      }
      await page.setViewportSize({width: 390, height: 844}); await nav('Home');
      if (capture) await page.screenshot({path: path.join(capture, 'h0-mobile.png'), fullPage: true});
    });
    await check('keyboard can reach controls and Escape closes without saving', async () => {
      await nav('Pending'); await inspect('School workshop preference requested');
      await page.keyboard.press('Tab'); assert.ok(await page.evaluate(() => document.activeElement.tagName === 'BUTTON'));
      await page.keyboard.press('Escape'); assert.equal(await dialog.count(), 0);
    });
    await check('no network requests, runtime errors or active external links', async () => {
      assert.deepEqual(requests, []); assert.deepEqual(errors, []);
      assert.deepEqual(await page.locator('a').evaluateAll(nodes => nodes.map(n => n.getAttribute('href'))), ['#main']);
    });
    console.log(`${passed} browser interaction checks passed (local-content harness, CSP bypassed; file:// not verified).`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
