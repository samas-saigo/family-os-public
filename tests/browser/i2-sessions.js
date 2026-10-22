'use strict';
// Real browser, actual CSP, actual loopback cookies. No security bypass or fixtures in JS.
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const http = require('node:http');
const path = require('node:path');
const {chromium} = require('playwright');
if (!process.argv.includes('--synthetic-only')) throw Error('Exact synthetic opt-in required');
const root = path.resolve(__dirname,'../..');
const python = process.env.I2_TEST_PYTHON || path.join(root,'.venv/bin/python');
const child = spawn(python,['-u','prototypes/i2-local-session/local_session.py','--synthetic-only'],{cwd:root,stdio:['pipe','pipe','pipe']});
let output = '';
child.stdout.on('data',b => { output += b.toString(); });
// Never dump process output, headers or cookies on failure.
child.stderr.on('data',() => {});
const pause = ms => new Promise(r => setTimeout(r,ms));
async function waitFor(fn) {
  for(let i=0;i<150;i++) { if (await fn()) return; await pause(100); }
  throw Error('Synthetic browser expectation timed out');
}
let browser, foreign;
(async()=>{
  let count = 0;
  await waitFor(() => /Open http:\/\/127\.0\.0\.1:\d+\//.test(output));
  const origin = output.match(/Open (http:\/\/127\.0\.0\.1:\d+)\//)[1];
  browser = await chromium.launch({executablePath:process.env.I2_CHROMIUM || '/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const left = await browser.newContext({viewport:{width:390,height:844}});
  const right = await browser.newContext({viewport:{width:320,height:844}});
  const a = await left.newPage(), b = await right.newPage();
  const problems = [];
  for(const p of [a,b]) p.on('pageerror',() => problems.push('browser-error'));
  async function ready(p) { await waitFor(() => p.evaluate(() => !busy)); }
  async function approve(p, peer) {
    await p.goto(origin+'/');
    await ready(p);
    await p.locator('#start').click();
    await waitFor(async()=>!(await p.locator('#request').isHidden()));
    const ticket = (await p.locator('#request').textContent()).match(/[0-9a-f]{16}/)[0];
    child.stdin.write(`approve ${ticket} ${peer}\n`);
    await waitFor(async()=> (await p.locator('#status').textContent()).includes(peer === 'clara'?'Clara':'Devon'));
  }
  await approve(a,'clara'); count++;
  await approve(b,'devon'); count++;
  const ca = (await left.cookies()).find(x=>x.name==='__Host-samas-i2');
  const cb = (await right.cookies()).find(x=>x.name==='__Host-samas-i2');
  assert(ca && cb && ca.value !== cb.value); count++;
  for(const [context,p] of [[left,a],[right,b]]) {
    const c = (await context.cookies()).find(x=>x.name==='__Host-samas-i2');
    assert(c.secure && c.httpOnly && c.sameSite==='Strict' && c.path==='/');
    assert.equal(await p.evaluate(()=>document.cookie),'');
    assert.equal(await p.evaluate(()=>localStorage.length+sessionStorage.length),0);
    assert(!(await p.content()).includes(c.value));
    assert(!p.url().includes(c.value));
    assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    const response = await p.request.get(origin+'/');
    assert(response.headers()['content-security-policy'].includes("connect-src 'self'"));
    assert.equal(response.headers()['access-control-allow-origin'],undefined);
    count++;
  }
  // Ordinary JS cannot replace an existing HttpOnly cookie with another identity.
  await a.evaluate(()=> { document.cookie='__Host-samas-i2=devon; Secure; Path=/; SameSite=Strict'; });
  assert((await left.cookies()).find(x=>x.name==='__Host-samas-i2').value===ca.value); count++;
  // Actual cross-origin preflight and simple POST both fail without changing sessions.
  foreign = http.createServer((req,res)=>res.end('<!doctype html><title>Synthetic foreign origin</title>'));
  await new Promise(r=>foreign.listen(0,'127.0.0.1',r));
  const cross = await browser.newPage();
  await cross.goto('http://127.0.0.1:'+foreign.address().port);
  const denied = await cross.evaluate(async target=>{
    try { await fetch(target+'/api/logout',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json','X-Samas-Intent':'local-session'},body:'{}'}); return false; }
    catch (_) { return true; }
  },origin);
  assert(denied); count++;
  await cross.evaluate(async target=>{
    try { await fetch(target+'/api/logout',{method:'POST',credentials:'include',mode:'no-cors',body:'{}'}); } catch (_) {}
  },origin);
  await ready(a); await a.locator('#check').click();
  await waitFor(async()=> (await a.locator('#status').textContent()).includes('Clara')); count++;
  await ready(a); await a.locator('#logout').click();
  await waitFor(async()=> (await a.locator('#status').textContent()).includes('已注销'));
  assert(!(await left.cookies()).some(x=>x.name==='__Host-samas-i2')); count++;
  await ready(b); await b.locator('#check').click();
  await waitFor(async()=> (await b.locator('#status').textContent()).includes('Devon')); count++;
  // Keyboard navigation and visible focus do not approve a session.
  await a.keyboard.press('Tab');
  assert(await a.evaluate(()=>document.activeElement.tagName==='BUTTON')); count++;
  child.stdin.write('quit\n');
  await waitFor(()=>child.exitCode!==null);
  await waitFor(async()=> (await b.locator('#status').textContent()).includes('会话不可用'));
  assert(!(await b.locator('#status').textContent()).includes('Devon')); count++;
  assert.equal(problems.length,0);
  console.log(`${count} real-browser I2 checks passed; synthetic-only; CSP active; no secret output.`);
})().catch(()=>{console.error('I2 synthetic browser checks failed (details withheld).');process.exitCode=1;}).finally(async()=>{
  if(child.exitCode===null) { child.stdin.write('quit\n'); await pause(1500); if(child.exitCode===null) child.kill(); }
  if(browser) await browser.close();
  if(foreign) foreign.close();
});
