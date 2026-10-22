'use strict';
const assert = require('node:assert/strict');
const path = require('node:path'), fs = require('node:fs');
const {spawn} = require('node:child_process');
if (!process.argv.includes('--synthetic-only')) throw Error('Exact synthetic opt-in required');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '../..'), pause = ms => new Promise(r => setTimeout(r, ms));
const baseline = process.argv.includes('--capture-before');
const child = spawn(process.env.I4B_TEST_PYTHON || path.join(root, '.venv/bin/python'),
  ['-u', 'tests/browser/a1-fixture-host.py', '--synthetic-only', ...(baseline ? ['--baseline'] : [])],
  {cwd: root, stdio: ['pipe', 'pipe', 'pipe']});
let output = '', browser, stage = 'startup', matrix = 0, checks = 0, submissions = 0;
const errors = [], external = [];
child.stdout.on('data', b => output += b); child.stderr.on('data', () => {});
async function wait(fn) { for (let i = 0; i < 300; i++) { if (await fn()) return; await pause(100); } throw Error('Synthetic expectation timed out'); }
async function command(value) {
  const start = output.length; child.stdin.write(value + '\n');
  await wait(() => /OK|UNAVAILABLE/.test(output.slice(start)));
  assert(!output.slice(start).includes('UNAVAILABLE'), 'Trusted fixture command failed: '+value.split(' ')[0]);
}
(async () => {
  await wait(() => /Open http:\/\/127\.0\.0\.1:\d+\//.test(output));
  const origin = output.match(/Open (http:\/\/127\.0\.0\.1:\d+)\//)[1];
  browser = await chromium.launch({executablePath: process.env.I4B_CHROMIUM || '/usr/bin/chromium', headless: true, args: ['--no-sandbox']});
  const images = path.join(root, 'docs/screenshots/ux2-a1-connected');
  const capture = process.argv.includes('--screenshots'); if (capture) fs.mkdirSync(images, {recursive: true});
  async function shot(p, name) { if (capture) { await p.mouse.move(0, 0); await p.screenshot({path: path.join(images, name + '.png')}); } }
  async function session(peer) {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
    await context.route('**/*', route => {
      if (new URL(route.request().url()).origin !== origin) { external.push('blocked'); return route.abort(); }
      return route.continue();
    });
    const p = await context.newPage(); p.setDefaultTimeout(12000);
    p.on('pageerror', () => errors.push('browser-error'));
    p.on('request', r => { if (['/api/tasks/edit-confirm', '/api/pending/accept'].includes(new URL(r.url()).pathname)) submissions++; });
    await p.goto(origin); await p.getByRole('button', {name: '发起请求', exact: true}).click();
    await p.locator('.connection-panel code').waitFor();
    await command('approve ' + await p.locator('.connection-panel code').textContent() + ' ' + peer);
    await p.locator('.stat strong').first().waitFor(); return {p, context};
  }
  const {p: a, context: ca} = await session('clara'), {p: b, context: cb} = await session('devon');
  async function nav(p, key) {
    if (['home', 'tasks', 'pending', 'upcoming', 'security'].includes(key)) await p.locator('#navigation button[data-view="' + key + '"]').click();
    else { const menu = p.locator('#secondary-menu'); if (!await menu.locator('button[data-view="' + key + '"]').isVisible()) await menu.locator('summary').click(); await menu.locator('button[data-view="' + key + '"]').click(); }
    if (key === 'home') await p.locator('.a1-home').waitFor();
    if (key === 'pending') await p.locator('.acceptance-status').waitFor();
    if (key === 'tasks') await p.locator('.connection-filter').waitFor();
  }
  async function reload(p) { await p.locator('#reload').click(); try { await p.locator('.a1-home').waitFor(); } catch (_) { throw Error('Home read failed: '+await p.locator('.connection-status').textContent().catch(()=> 'no status')); } }
  async function language(p, locale) {
    const menu = p.locator('#secondary-menu');
    if (!await p.locator('#language').isVisible()) await menu.locator('summary').click();
    await p.locator('#language').selectOption(locale);
    if (await menu.getAttribute('open') !== null) await menu.locator('summary').click();
  }
  async function colors(p, theme) { await nav(p, 'settings'); await p.locator('#appearance').selectOption(theme); await nav(p, 'home'); }
  async function counts(p, tasks, pending) {
    await wait(async () => await p.locator('[data-home-count="tasks"] strong').textContent().catch(() => null) === String(tasks));
    if (pending !== undefined) assert.equal(await p.locator('[data-home-count="pending"] strong').textContent(), String(pending));
  }
  async function fits(p) {
    assert(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Horizontal overflow');
    assert.deepEqual(await p.evaluate(() => [...document.querySelectorAll('button,select,summary')].filter(n => n.checkVisibility()).filter(n => {
      const r = n.getBoundingClientRect(); return n.scrollWidth > n.clientWidth + 1 || r.height < 44 || r.left < -.5 || r.right > innerWidth + .5;
    }).map(n => n.tagName)), []);
  }
  async function failed(p) { await p.locator('.connection-status').filter({hasText:/无法验证|连接失败|格式不匹配|could not be verified|Connection failed|contract mismatch/}).waitFor(); }
  async function emptyProtected(p) {
    assert.equal(await p.locator('.a1-home,article,[data-home-pending],time').count(), 0);
    assert.equal(await p.locator('#member-status').textContent(), '');
    assert(!await p.getByRole('dialog').isVisible()); assert.equal(await p.locator('#dialog-body').textContent(), '');
  }
  if (baseline) {
    assert(capture); await shot(a, 'before-clara-1440'); await b.setViewportSize({width: 390, height: 844}); await shot(b, 'before-devon-390');
    console.log('2 actual merged-I4b baseline captures; no regression claim.'); return;
  }
  const initial = {};
  for (const [peer, p, number] of [['clara', a, 3], ['devon', b, 2]]) {
    await counts(p, number); initial[peer] = Number(await p.locator('[data-home-count="pending"] strong').textContent());
    assert(await p.locator('h1').textContent().then(t => t.includes(peer === 'clara' ? 'Clara' : 'Devon')));
    assert.equal(await p.locator('article').count(), number);
    assert(await p.locator('.a1-task').filter({hasText: '未设置日期'}).count() >= 1);
    assert.equal(await p.locator('.a1-date time').count(), 1);
    assert(await p.locator('.a1-support').textContent().then(t => t.includes('当前未连接')));
    assert.equal(await p.locator('article').filter({hasText: '已完成'}).count(), 1);
  }
  for (const [peer, p] of [['clara', a], ['devon', b]]) {
    await nav(p, 'pending'); assert.equal(await p.locator('[data-pending="i4a-visit"]').count(), peer === 'devon' ? 1 : 0); await nav(p, 'home');
  } checks++;
  stage = 'matrix';
  for (const [peer, p, number] of [['clara', a, 3], ['devon', b, 2]]) for (const locale of ['zh-CN', 'en-US']) for (const theme of ['light', 'dark']) {
    console.log('A1 matrix: '+peer+'/'+locale+'/'+theme);
    await language(p, locale); await colors(p, theme);
    for (const width of [1440, 1152, 960, 390, 320]) {
      stage = [peer, locale, theme, width].join('/'); await p.setViewportSize({width, height: width > 730 ? 1000 : 844});
      await nav(p, 'home'); await counts(p, number, initial[peer]); await fits(p);
      assert.equal(await p.locator('.stat').count(), 2);
      assert.equal(await p.locator('.a1-task').count(), number);
      if (peer === 'clara') assert.equal(await p.locator('[data-home-pending="i4a-visit"]').count(), 0);
      assert.equal(await p.locator('[data-home-pending="i4a-offer"],[data-home-pending="i4a-notice"]').count(), 0);
      const boxes = await p.evaluate(() => ({workspace: document.querySelector('.workspace').getBoundingClientRect().y,
        toolbar: document.querySelector('.topbar').getBoundingClientRect().y, main: document.querySelector('main').getBoundingClientRect().y}));
      if (width > 730) assert.equal(boxes.workspace, 0);
      if (width <= 730) { const first = await p.locator('.a1-task h3').first().boundingBox(), bottom = await p.locator('.nav-main').boundingBox(); assert(first.y + first.height < bottom.y); }
      const long = locale === 'zh-CN' ? '整理虚构学校活动的无障碍出行安排并核对共同参与细节（仅测试换行）' : 'Coordinate fictional school arrival, accessible travel arrangements and accompanying adults (layout stress only)';
      await p.locator('.a1-task h3').first().evaluate((n, text) => n.textContent = text, long); await fits(p); await reload(p);
      const name = ['home', peer, locale === 'zh-CN' ? 'zh' : 'en', theme, width].join('-');
      if ((width === 1440 && (locale === 'zh-CN' || theme === 'dark')) || (width <= 390 && ((peer === 'clara' && locale === 'zh-CN') || (peer === 'devon' && locale === 'en-US' && theme === 'dark')))) await shot(p, name);
      for (const view of ['upcoming', 'security', 'home']) {
        await nav(p, view); await fits(p);
        const actual = await p.evaluate(() => [document.querySelector('.topbar').getBoundingClientRect().y, document.querySelector('main').getBoundingClientRect().y]);
        assert.deepEqual(actual, [boxes.toolbar, boxes.main]);
      }
      matrix++;
    }
  }
  assert.equal(submissions, 0); checks++;
  // Real authorization reads must leave focused controls mounted over two 5-second polls.
  stage = 'poll-focus'; await a.setViewportSize({width: 1440, height: 1000}); await language(a, 'zh-CN'); await colors(a, 'light');
  await a.locator('[data-home-count="tasks"]').focus();
  const focused = await a.locator('[data-home-count="tasks"]').elementHandle(); let polls = 0;
  const observer = r => { if (new URL(r.url()).pathname === '/api/pending' && r.status() === 200) polls++; }; a.on('response', observer);
  const started = Date.now(); await wait(() => polls >= 2 && Date.now() - started >= 10000); a.off('response', observer);
  assert(await focused.evaluate(n => n === document.activeElement)); checks++;
  const school = p => p.locator('.a1-task').filter({hasText: '2035-06-12'});
  async function detail(p) { await school(p).getByRole('button', {name: /^(详情|Details)$/}).click(); await p.locator('#edit-assignee').waitFor(); }
  stage = 'original-writes'; console.log('A1 stage: '+stage); await detail(a); assert.equal(await a.locator('#edit-assignee').inputValue(), 'joint');
  await a.locator('#edit-assignee').selectOption('i2-devon'); await a.getByRole('button', {name: '调整分工', exact: true}).click();
  await a.getByRole('button', {name: '确认修改', exact: true}).waitFor(); await a.getByRole('button', {name: '取消', exact: true}).click(); assert.equal(submissions, 0); checks++;
  await detail(a); await a.locator('#edit-assignee').selectOption('i2-devon'); await a.getByRole('button', {name: '调整分工', exact: true}).click();
  await a.getByRole('button', {name: '确认修改', exact: true}).click(); await a.getByText('家庭待办已更新', {exact: true}).waitFor();
  await nav(a, 'home'); await nav(b, 'home'); await counts(a, 3); await counts(b, 2);
  assert.match(await school(a).textContent(), /Devon/); assert.match(await school(b).textContent(), /Devon/); checks++;
  await detail(a); await a.getByRole('button', {name: '标记完成', exact: true}).click(); await a.getByRole('button', {name: '确认修改', exact: true}).click();
  await a.getByText('家庭待办已更新', {exact: true}).waitFor(); await nav(a, 'home'); await counts(a, 3);
  assert.match(await school(a).textContent(), /已完成/); await shot(a, 'after-completed-home'); checks++;
  await nav(a, 'pending'); await a.locator('[data-pending="i4a-school"] button').click(); await a.getByRole('button', {name: '确认接受', exact: true}).waitFor();
  await a.getByRole('button', {name: '取消', exact: true}).click(); assert.equal(submissions, 2); checks++;
  await a.locator('[data-pending="i4a-school"] button').click(); await a.getByRole('button', {name: '确认接受', exact: true}).click();
  await a.getByText('已加入家庭待办', {exact: true}).waitFor(); await nav(a, 'home'); await counts(a, 4, initial.clara - 1);
  await nav(b, 'home'); await counts(b, 3, initial.devon - 1); assert.equal(submissions, 3); checks++;
  // The Home entry still uses the exact original cross-operation receipt and UNKNOWN coordinator.
  await detail(a); await a.getByRole('button', {name: '恢复未完成', exact: true}).click(); await command('unknown');
  await a.getByRole('button', {name: '确认修改', exact: true}).click(); await a.getByText('结果尚未确认。不要重复提交，请核对最近操作。', {exact: true}).waitFor();
  assert.equal(submissions, 4); await reload(a); await command('recover'); await a.getByRole('button', {name: '核对最近操作', exact: true}).click();
  await a.getByText('家庭待办已更新', {exact: true}).waitFor(); await nav(a, 'home'); assert.equal(submissions, 4); checks++;
  stage = 'fail-closed'; console.log('A1 stage: '+stage);
  for (const kind of ['fail-tasks', 'fail-pending']) {
    stage='fault-'+kind; console.log('A1 stage: '+stage); await command(kind); await a.locator('#reload').click(); await failed(a); await emptyProtected(a);
    await shot(a, kind + '-safe'); await command('recover'); await reload(a); await counts(a, 4); checks++;
  }
  for (const endpoint of ['tasks', 'pending']) {
    stage='contract-'+endpoint; console.log('A1 stage: '+stage); await a.route('**/api/' + endpoint + '?**', r => r.fulfill({status: 200, contentType: 'application/json', body: '{}'}));
    await a.locator('#reload').click(); await failed(a); await emptyProtected(a);
    await a.unroute('**/api/' + endpoint + '?**'); await reload(a); checks++;
  }
  stage='connection-abort'; console.log('A1 stage: '+stage); await a.route('**/api/pending?**', r => r.abort()); await a.locator('#reload').click(); await failed(a); await emptyProtected(a);
  await shot(a,'connection-failed-safe'); await a.unroute('**/api/pending?**'); await reload(a); checks++;
  stage='connection-timeout'; console.log('A1 stage: '+stage); let delayed; await a.route('**/api/pending?**', r => { delayed = r; }); await a.locator('#reload').click();
  await a.locator('.connection-status').filter({hasText: /连接失败/}).waitFor(); await emptyProtected(a);
  await a.unroute('**/api/pending?**'); if (delayed) await delayed.abort().catch(() => {}); await reload(a); checks++;
  // Late valid data from a prior request must not overwrite the new page/current rights.
  stage='late-response'; console.log('A1 stage: '+stage); let held, old; await a.route('**/api/tasks?**', async r => { old = await (await r.fetch()).text(); held = r; });
  await a.locator('#reload').click(); await wait(() => held);
  await nav(a, 'pending'); await held.fulfill({status: 200, contentType: 'application/json', body: old}); await a.unroute('**/api/tasks?**'); await pause(100);
  assert.equal(await a.locator('.a1-home').count(), 0); assert.equal(await a.locator('main').getAttribute('data-view'), 'pending'); checks++;
  // A current member change between the independent reads must not publish a mixed pair.
  stage='member-mismatch'; console.log('A1 stage: '+stage); await nav(a,'home'); const originalCookies = await ca.cookies(); let mixed, mixedBody;
  await a.route('**/api/pending?**', async r => { mixedBody = await (await r.fetch()).text(); mixed = r; });
  await a.locator('#reload').click(); await wait(() => mixed); await ca.addCookies(await cb.cookies());
  await mixed.fulfill({status:200,contentType:'application/json',body:mixedBody}); await a.unroute('**/api/pending?**');
  await failed(a); await emptyProtected(a);
  stage='member-mismatch-new-session'; await reload(a); await counts(a,3,initial.devon-1); assert.equal(await a.locator('#member-status').textContent(),'Devon');
  stage='member-mismatch-original-session'; await ca.addCookies(originalCookies); await reload(a); await counts(a,4,initial.clara-1); checks++;
  stage = 'permission-pages'; console.log('A1 stage: '+stage); await nav(a, 'home'); await command('pending-revoke clara'); await reload(a); await counts(a, 4, 0);
  assert.equal(await a.locator('[data-home-pending]').count(), 0); await shot(a, 'empty-pending-home');
  await nav(b, 'home'); await counts(b, 3, initial.devon - 1); checks++;
  await command('tasks-revoke clara'); await reload(a); await counts(a, 0, 0); assert.equal(await a.locator('article,time').count(), 0); checks++;
  await command('many'); await reload(b); await counts(b, 17); assert.equal(await b.locator('.a1-task').count(), 12);
  assert.match(await b.locator('.a1-section').first().textContent(), /12.*17/); checks++;
  await b.getByRole('button', {name: 'View all household tasks', exact: true}).click(); await b.locator('.connection-filter').waitFor();
  await b.getByRole('button', {name: 'Next page', exact: true}).click(); await wait(async () => await b.locator('article').count() === 5);
  await nav(b, 'home'); await counts(b, 17); assert.equal(await b.locator('.a1-task').count(), 12); checks++;
  await command('many-pending'); await reload(b); await counts(b,17,initial.devon+13);
  assert.equal(await b.locator('[data-home-pending]').count(),3);
  await b.getByRole('button',{name:'View Pending',exact:true}).click(); await b.locator('.acceptance-status').waitFor();
  assert.equal(await b.locator('[data-pending]').count(),12);
  await b.getByRole('button',{name:'Next page',exact:true}).click(); await wait(async()=>await b.locator('[data-pending]').count()===initial.devon+1);
  await nav(b,'home'); await counts(b,17,initial.devon+13); checks++;
  await command('no-dates'); await reload(b); assert.equal(await b.locator('.a1-date').count(), 0);
  assert.equal(await b.locator('.a1-task').filter({hasText: 'No date set'}).count(), 12); await shot(b, 'no-dates-home'); checks++;
  // Exchange only fictional test cookies, simulating another independently established session.
  // The application never receives or chooses these secrets via JS or a member selector.
  await ca.addCookies(await cb.cookies()); await reload(a); await counts(a, 17, initial.devon + 13);
  assert.equal(await a.locator('#member-status').textContent(), 'Devon'); assert.match(await a.locator('h1').textContent(), /Devon/); checks++;
  await command('member-revoke devon'); await failed(a); await emptyProtected(a);
  await shot(a, 'authorization-failed-safe'); checks++;
  assert.deepEqual(errors, []); assert.deepEqual(external, []);
  assert.equal(submissions, 4);
  console.log(matrix + ' actual-origin A1 layout combinations and ' + checks + ' safety/interaction checks passed; real I4b SQL/cookies, no external requests.');
})().catch(e => { console.error('A1 failed at ' + stage + ': ' + e.message); process.exitCode = 1; })
  .finally(async () => { if (browser) await browser.close(); if (child.exitCode === null) { child.stdin.write('quit\n'); await pause(1000); if (child.exitCode === null) child.kill(); } });
