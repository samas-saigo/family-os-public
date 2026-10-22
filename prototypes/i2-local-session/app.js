'use strict';
// No bearer/identity input, storage, task model or permission inference.
const statusNode = document.getElementById('status');
const requestNode = document.getElementById('request');
const buttons = Object.fromEntries(['start','check','cancel','logout'].map(id => [id, document.getElementById(id)]));
let busy = false;
let waiting = false;
let timer;
function clearView() {
  statusNode.textContent = '正在检查当前测试会话。';
  requestNode.textContent = '';
  requestNode.hidden = true;
  buttons.start.disabled = true;
  buttons.cancel.hidden = true;
  buttons.logout.hidden = true;
}
async function call(action) {
  if (busy) return;
  busy = true;
  waiting = false;
  clearTimeout(timer);
  clearView(); // Never retain a previously authorized member during failure/loading.
  try {
    const response = await fetch('/api/' + action, {
      method:'POST', credentials:'same-origin', mode:'same-origin', cache:'no-store',
      headers:{'Content-Type':'application/json', 'X-Samas-Intent':'local-session'},
      body:'{}', signal:AbortSignal.timeout(5000), redirect:'error'
    });
    if (!response.ok || response.headers.get('content-type') !== 'application/json') throw Error();
    const raw = await response.text();
    if (raw.length > 512) throw Error();
    const result = JSON.parse(raw);
    if (result.state === 'active' && Object.keys(result).sort().join() === 'member,state' &&
        ['i2-clara','i2-devon'].includes(result.member)) {
      statusNode.textContent = '当前虚构成员：' + (result.member === 'i2-clara' ? 'Clara' : 'Devon') + '（仅开发测试）';
      buttons.logout.hidden = false;
      waiting = true; // Fresh status check also bounds stale display after failure.
    } else if (result.state === 'waiting' && Object.keys(result).sort().join() === 'request_id,state' &&
        /^[0-9a-f]{16}$/.test(result.request_id)) {
      statusNode.textContent = '等待启动终端批准。请求将在两分钟后失效。';
      requestNode.textContent = '核对请求编号：' + result.request_id;
      requestNode.hidden = false;
      buttons.cancel.hidden = false;
      waiting = true;
    } else if (['logged_out','cancelled'].includes(result.state) && Object.keys(result).join() === 'state') {
      statusNode.textContent = result.state === 'logged_out' ? '测试会话已注销。' : '请求已取消，当前连接已停止使用。';
      buttons.start.disabled = false;
    } else if (result.state === 'unknown' && Object.keys(result).join() === 'state') {
      statusNode.textContent = '注销结果无法确认。当前连接已停止使用；请结束本地测试服务，勿自动重试。';
    } else throw Error();
  } catch (_) {
    clearView();
    statusNode.textContent = '会话不可用。请确认本地服务、终端批准和浏览器 Cookie 支持；不会使用离线数据替代。';
    buttons.start.disabled = false;
  } finally {
    busy = false;
    // Polling only checks current state; it never approves/retries issuance.
    if (waiting) timer = setTimeout(() => call('session'), 2000);
  }
}
for (const action of ['start','cancel','logout']) buttons[action].addEventListener('click', () => call(action));
buttons.check.addEventListener('click', () => call('session'));
addEventListener('pagehide', () => { clearTimeout(timer); clearView(); });
addEventListener('pageshow', event => { if (event.persisted) call('session'); });
call('session');
