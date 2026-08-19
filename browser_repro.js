// CDP-based browser reproduction: click attendance buttons, capture console + network.
const { spawn } = require('child_process');
const path = require('path');
const os = require('os');

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9222;
const USER_DIR = path.join(os.tmpdir(), 'salahmate-cdp-' + Date.now());
const BASE = 'http://127.0.0.1:5000';

const sleep = ms => new Promise(r => setTimeout(r, ms));

class CDP {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); }
  static async connect(url) {
    const ws = new WebSocket(url);
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
    return new CDP(ws);
  }
  send(method, params = {}) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((res, rej) => this.pending.set(id, { res, rej }));
  }
  on(method, cb) {
    this.ws.addEventListener('message', ev => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) {
        const p = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? p.rej(new Error(JSON.stringify(msg.error))) : p.res(msg.result);
      } else if (msg.method === method) {
        cb(msg.params);
      }
    });
  }
}

async function main() {
  const chrome = spawn(CHROME, [
    '--headless=new', '--remote-debugging-port=' + PORT,
    '--user-data-dir=' + USER_DIR, '--no-first-run', '--disable-gpu',
    '--window-size=1400,1000', 'about:blank'
  ]);
  chrome.on('error', e => { console.error('CHROME LAUNCH ERROR:', e.message); process.exit(1); });

  let targets;
  for (let i = 0; i < 50; i++) {
    try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json(); break; }
    catch (e) { await sleep(200); }
  }
  if (!targets) { console.error('No CDP endpoint'); process.exit(1); }

  const page = targets.find(t => t.type === 'page');
  const cdp = await CDP.connect(page.webSocketDebuggerUrl);

  cdp.on('Runtime.consoleAPICalled', p => {
    const args = (p.args || []).map(a => a.value ?? a.description ?? '').join(' ');
    console.log('[CONSOLE]', args);
  });
  cdp.on('Runtime.exceptionThrown', p => {
    console.log('[EXCEPTION]', JSON.stringify(p.exceptionDetails).slice(0, 1500));
  });
  cdp.on('Log.entryAdded', p => {
    if (p.entry.level === 'error') console.log('[LOG-ERROR]', p.entry.text);
  });
  cdp.on('Network.requestWillBeSent', p => {
    if (p.request.url.includes('/attendance/update')) {
      console.log('[NET-REQ]', p.request.method, p.request.url, 'BODY:', p.request.postData);
    }
  });
  cdp.on('Network.responseReceived', p => {
    if (p.response.url.includes('/attendance/update')) {
      console.log('[NET-RES]', p.response.status, p.response.url);
    }
  });

  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  await cdp.send('Log.enable');
  await cdp.send('Network.enable');

  const evalJS = async expr => {
    const r = await cdp.send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) { console.error('[EVAL-ERR]', JSON.stringify(r.exceptionDetails).slice(0, 1200)); return 'EVAL-ERROR'; }
    return r.result.value;
  };

  // Login
  await cdp.send('Page.navigate', { url: BASE + '/login' });
  await sleep(1800);
  await evalJS(`document.querySelector('#username').value='scheck';
    document.querySelector('#password').value='TestPass123';
    document.querySelector('form.auth-form').submit(); true`);
  await sleep(2200);
  console.log('[URL-AFTER-LOGIN]', await evalJS('location.href'));

  // Attendance page (direct load = "today, without visiting Calendar")
  await cdp.send('Page.navigate', { url: BASE + '/attendance' });
  await sleep(2500);
  console.log('[URL-ATT]', await evalJS('location.href'));
  console.log('[DATE-HEADER]', await evalJS(`document.querySelector('.page-header p') ? document.querySelector('.page-header p').textContent : 'NONE'`));
  console.log('[DATE-PICKER]', await evalJS(`document.getElementById('date-picker') ? document.getElementById('date-picker').value : 'NONE'`));
  console.log('[BTN-COUNT]', await evalJS(`document.querySelectorAll('.btn-status').length`));
  console.log('[PRAYER-JS-FN]', await evalJS(`typeof updatePrayer`));
  console.log('[INITIALIZED]', await evalJS(`window.__prayerInitialized`));

  // Click 1: Fajr -> qaza
  console.log('[CLICK-1]', await evalJS(`(function(){
    const btn = document.querySelector('.prayer-item[data-prayer="Fajr"] .btn-status[data-status="qaza"]');
    if (!btn) return 'NO-BUTTON';
    btn.click();
    return 'clicked prayer=' + btn.dataset.prayer + ' status=' + btn.dataset.status + ' date=' + btn.dataset.date;
  })()`));
  await sleep(3000);
  console.log('[FAJR-AFTER-CLICK1]', await evalJS(`(function(){
    const it = document.querySelector('.prayer-item[data-prayer="Fajr"]');
    const active = it ? it.querySelector('.btn-status.active') : null;
    return active ? 'ACTIVE=' + active.dataset.status : 'NO-ACTIVE';
  })()`));
  console.log('[TOAST]', await evalJS(`document.querySelector('.toast-container-salahmate') ? document.querySelector('.toast-container-salahmate').innerText : 'NONE'`));

  // Click 2: Fajr -> missed (change again)
  await evalJS(`document.querySelector('.prayer-item[data-prayer="Fajr"] .btn-status[data-status="missed"]').click(); true`);
  await sleep(2500);
  console.log('[FAJR-AFTER-CLICK2]', await evalJS(`(function(){
    const it = document.querySelector('.prayer-item[data-prayer="Fajr"]');
    const active = it ? it.querySelector('.btn-status.active') : null;
    return active ? 'ACTIVE=' + active.dataset.status : 'NO-ACTIVE';
  })()`));

  // What buttons exist for male-style Jamaat? (scheck is female)
  console.log('[FAJR-BTNS]', await evalJS(`Array.from(document.querySelectorAll('.prayer-item[data-prayer="Fajr"] .btn-status')).map(b => b.dataset.status + '(' + b.textContent.trim() + ')').join(', ')`));
  console.log('[DHUHR-BTNS]', await evalJS(`Array.from(document.querySelectorAll('.prayer-item[data-prayer="Dhuhr"] .btn-status')).map(b => b.dataset.status).join(',')`));

  await sleep(1000);
  chrome.kill();
  process.exit(0);
}

main().catch(e => { console.error('FATAL', e); process.exit(1); });