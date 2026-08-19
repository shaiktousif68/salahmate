// Verify premium 3D player renders for ALL translations (English, Urdu, Telugu)
const { spawn } = require('child_process');
const path = require('path');
const os = require('os');

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9245;
const USER_DIR = path.join(os.tmpdir(), 'salahmate-player-cdp-' + Date.now());
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

  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');

  const evalJS = async expr => {
    const r = await cdp.send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) {
      const detail = JSON.stringify(r.exceptionDetails).slice(0, 800);
      console.error('[EVAL-ERR]', detail);
      return 'EVAL-ERROR: ' + detail;
    }
    return r.result.value;
  };

  // Register and login
  await cdp.send('Page.navigate', { url: BASE + '/register' });
  await sleep(1800);
  const u = 'playercheck' + Date.now().toString().slice(-6);
  await evalJS(`(function(){
    document.querySelector('#full_name').value = 'Player Check';
    document.querySelector('#username').value = '${u}';
    document.querySelector('#email').value = '${u}@test.com';
    document.querySelector('#password').value = 'TestPass123';
    document.querySelector('#confirm_password').value = 'TestPass123';
    document.querySelector('input[name="gender"][value="male"]').checked = true;
    document.querySelector('form').submit();
    return true;
  })()`);
  await sleep(2200);
  await cdp.send('Page.navigate', { url: BASE + '/login' });
  await sleep(1500);
  await evalJS(`(function(){
    document.querySelector('#username').value = '${u}';
    document.querySelector('#password').value = 'TestPass123';
    document.querySelector('form.auth-form').submit();
    return true;
  })()`);
  await sleep(2500);
  console.log('[LOGIN-URL]', await evalJS('location.href'));

  // Test each translation on Surah 1
  const translations = {
    'English': 'en.sahih',
    'Urdu': 'ur.jalandhry',
    'Telugu': 'te.zekr'
  };

  for (const [name, trans] of Object.entries(translations)) {
    console.log(`\n===== SURAH 1 — ${name} (${trans}) =====`);
    await cdp.send('Page.navigate', { url: `${BASE}/quran/surah/1?translation=${trans}` });
    await sleep(3500);

    const check = await evalJS(`(function(){
      const player = document.getElementById('audio-player');
      const premium3dTop = document.querySelector('.audio-player-3d-top');
      const iconWrap = document.getElementById('audio-player-icon-wrap');
      const rings = document.querySelectorAll('.play-ring');
      const waveform = document.getElementById('audio-waveform');
      const progress = document.getElementById('audio-progress');
      // Check for native audio elements
      const nativeAudioEls = document.querySelectorAll('audio');
      let visibleNativeControls = 0;
      nativeAudioEls.forEach(a => {
        const style = getComputedStyle(a);
        if (style.display !== 'none' && !style.visibility === 'hidden') {
          visibleNativeControls++;
        }
      });
      return {
        premiumPlayerExists: !!player,
        premium3dTopExists: !!premium3dTop,
        iconWrapExists: !!iconWrap,
        ringCount: rings.length,
        waveformExists: !!waveform,
        progressExists: !!progress,
        nativeAudioEls: nativeAudioEls.length,
        nativeAudioWithControls: Array.from(nativeAudioEls).filter(a => a.hasAttribute('controls')).length,
        playerDisplay: player ? getComputedStyle(player).display : 'N/A'
      };
    })()`);
    console.log('[PLAYER-CHECK]', JSON.stringify(check, null, 2));

    // Click first audio button to ensure player works
    const playResult = await evalJS(`(function(){
      const btn = document.querySelector('.audio-btn');
      if (!btn) return 'NO BTN';
      btn.click();
      return 'CLICKED';
    })()`);
    await sleep(3500);
    const afterPlay = await evalJS(`(function(){
      const player = document.getElementById('audio-player');
      return {
        playerDisplay: player ? player.style.display : 'NONE',
        hasPlayingClass: player ? player.classList.contains('is-playing') : false,
        iconClass: document.getElementById('audio-player-icon') ? document.getElementById('audio-player-icon').className : 'NONE'
      };
    })()`);
    console.log('[AFTER-PLAY]', JSON.stringify(afterPlay));
  }

  // Also test Para reader with English
  console.log(`\n===== PARA 1 — English =====`);
  await cdp.send('Page.navigate', { url: `${BASE}/quran/para/1?translation=en.sahih` });
  await sleep(3500);
  const paraCheck = await evalJS(`(function(){
    const player = document.getElementById('audio-player');
    const premium3dTop = document.querySelector('.audio-player-3d-top');
    const iconWrap = document.getElementById('audio-player-icon-wrap');
    const nativeAudioEls = document.querySelectorAll('audio');
    return {
      premiumPlayerExists: !!player,
      premium3dTopExists: !!premium3dTop,
      iconWrapExists: !!iconWrap,
      nativeAudioEls: nativeAudioEls.length,
      nativeAudioWithControls: Array.from(nativeAudioEls).filter(a => a.hasAttribute('controls')).length
    };
  })()`);
  console.log('[PARA-PLAYER-CHECK]', JSON.stringify(paraCheck, null, 2));

  await sleep(500);
  chrome.kill();
  process.exit(0);
}

main().catch(e => { console.error('FATAL', e); process.exit(1); });