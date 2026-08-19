// Deep browser-level investigation of the actual rendered Quran player
const { spawn } = require('child_process');
const path = require('path');
const os = require('os');

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9250;
const USER_DIR = path.join(os.tmpdir(), 'salahmate-deep-cdp-' + Date.now());
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

  const consoleErrors = [];
  cdp.on('Runtime.consoleAPICalled', p => {
    const type = p.type || 'log';
    const args = (p.args || []).map(a => a.value ?? a.description ?? '').join(' ');
    if (type === 'error' || type === 'warning') consoleErrors.push(`[${type}] ${args}`);
  });
  cdp.on('Runtime.exceptionThrown', p => {
    consoleErrors.push('[EXCEPTION] ' + JSON.stringify(p.exceptionDetails).slice(0, 1000));
  });
  cdp.on('Log.entryAdded', p => {
    if (p.entry.level === 'error') consoleErrors.push('[LOG-ERROR] ' + p.entry.text);
  });

  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  await cdp.send('Log.enable');

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
  const u = 'deepcheck' + Date.now().toString().slice(-6);
  await evalJS(`(function(){
    document.querySelector('#full_name').value = 'Deep Check';
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

  // Test English translation (default)
  console.log('\n===== ENGLISH (en.sahih) — DEEP INVESTIGATION =====');
  await cdp.send('Page.navigate', { url: `${BASE}/quran/surah/1?translation=en.sahih` });
  await sleep(4000);

  // Check the actual rendered DOM structure
  const domCheck = await evalJS(`(function(){
    // Check all audio-related elements
    const allAudio = document.querySelectorAll('audio');
    const player = document.getElementById('audio-player');
    const premium3dTop = document.querySelector('.audio-player-3d-top');
    const iconWrap = document.getElementById('audio-player-icon-wrap');
    const waveform = document.getElementById('audio-waveform');
    const progress = document.getElementById('audio-progress');
    const speedBtn = document.getElementById('audio-speed-btn');
    const repeatBtn = document.getElementById('audio-repeat-btn');
    const prevBtn = document.getElementById('audio-prev');
    const nextBtn = document.getElementById('audio-next');
    const playPause = document.getElementById('audio-play-pause');

    // Check computed styles
    const playerStyle = player ? getComputedStyle(player) : null;
    const premiumStyle = premium3dTop ? getComputedStyle(premium3dTop) : null;

    // Check if quran.js initialized
    const quranInit = window.__quranAudioInitialized;

    // Check for any old player elements
    const oldPlayerEls = document.querySelectorAll('.old-player, .native-player, audio[controls]');

    return {
      // Audio elements
      audioElementCount: allAudio.length,
      audioWithControls: Array.from(allAudio).filter(a => a.hasAttribute('controls')).length,
      audioDisplay: allAudio.length ? getComputedStyle(allAudio[0]).display : 'N/A',

      // Premium player elements
      premiumPlayerExists: !!player,
      premium3dTopExists: !!premium3dTop,
      iconWrapExists: !!iconWrap,
      waveformExists: !!waveform,
      progressExists: !!progress,
      speedBtnExists: !!speedBtn,
      repeatBtnExists: !!repeatBtn,
      prevBtnExists: !!prevBtn,
      nextBtnExists: !!nextBtn,
      playPauseExists: !!playPause,

      // Computed styles
      playerDisplay: playerStyle ? playerStyle.display : 'N/A',
      playerVisibility: playerStyle ? playerStyle.visibility : 'N/A',
      playerOpacity: playerStyle ? playerStyle.opacity : 'N/A',
      premium3dTopDisplay: premiumStyle ? premiumStyle.display : 'N/A',

      // JS state
      quranAudioInitialized: quranInit,

      // Old player check
      oldPlayerElements: oldPlayerEls.length,

      // Check for any element with 'controls' attribute
      elementsWithControls: document.querySelectorAll('[controls]').length
    };
  })()`);
  console.log('[DOM-CHECK]', JSON.stringify(domCheck, null, 2));

  // Check if the premium player is actually visible when we click play
  console.log('\n--- Clicking play on Ayah 1 ---');
  await evalJS(`document.querySelector('.audio-btn').click(); true`);
  await sleep(4000);

  const afterPlay = await evalJS(`(function(){
    const player = document.getElementById('audio-player');
    const playerStyle = player ? getComputedStyle(player) : null;
    const icon = document.getElementById('audio-player-icon');
    const waveform = document.getElementById('audio-waveform');
    const waveformStyle = waveform ? getComputedStyle(waveform) : null;
    const progressFill = document.getElementById('audio-progress-fill');
    const progressFillStyle = progressFill ? getComputedStyle(progressFill) : null;

    return {
      playerDisplay: playerStyle ? playerStyle.display : 'N/A',
      playerVisibility: playerStyle ? playerStyle.visibility : 'N/A',
      playerOpacity: playerStyle ? playerStyle.opacity : 'N/A',
      playerHasPlayingClass: player ? player.classList.contains('is-playing') : false,
      iconClass: icon ? icon.className : 'NONE',
      waveformDisplay: waveformStyle ? waveformStyle.display : 'N/A',
      waveformOpacity: waveformStyle ? waveformStyle.opacity : 'N/A',
      progressFillWidth: progressFillStyle ? progressFillStyle.width : 'N/A',
      // Check if any native controls are visible
      visibleAudioControls: Array.from(document.querySelectorAll('audio')).filter(a => {
        const s = getComputedStyle(a);
        return s.display !== 'none' && a.hasAttribute('controls');
      }).length
    };
  })()`);
  console.log('[AFTER-PLAY]', JSON.stringify(afterPlay, null, 2));

  // Check for any JS errors
  console.log('\n===== CONSOLE ERRORS =====');
  if (consoleErrors.length === 0) {
    console.log('No console errors detected.');
  } else {
    console.log('Console errors found (' + consoleErrors.length + '):');
    consoleErrors.slice(0, 20).forEach(e => console.log('  ' + e));
  }

  await sleep(500);
  chrome.kill();
  process.exit(0);
}

main().catch(e => { console.error('FATAL', e); process.exit(1); });