// CDP-based browser verification for the premium 3D Quran audio player.
// Verifies the actual rendered DOM for the 3D player in both Surah and Para pages.
const { spawn } = require('child_process');
const path = require('path');
const os = require('os');

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9223;
const USER_DIR = path.join(os.tmpdir(), 'salahmate-quran-cdp-' + Date.now());
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
    consoleErrors.push('[EXCEPTION] ' + JSON.stringify(p.exceptionDetails).slice(0, 800));
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

  // --- Register a fresh user, then login ---
  await cdp.send('Page.navigate', { url: BASE + '/register' });
  await sleep(1500);

  // Generate the username deterministically so we can use it after navigation
  const testUsername = 'qurancheck' + Date.now().toString().slice(-6);
  const testEmail = testUsername + '@test.com';
  await evalJS(`(function(){
    const username = '${testUsername}';
    document.querySelector('#full_name').value = 'Quran Checker';
    document.querySelector('#username').value = username;
    document.querySelector('#email').value = '${testEmail}';
    document.querySelector('#password').value = 'TestPass123';
    document.querySelector('#confirm_password').value = 'TestPass123';
    document.querySelector('input[name="gender"][value="male"]').checked = true;
    document.querySelector('form').submit();
    return true;
  })()`);
  await sleep(2200);
  console.log('[REGISTER-URL]', await evalJS('location.href'));

  // Registration always redirects to /login — log in with the new credentials
  await cdp.send('Page.navigate', { url: BASE + '/login' });
  await sleep(1500);
  await evalJS(`(function(){
    document.querySelector('#username').value = '${testUsername}';
    document.querySelector('#password').value = 'TestPass123';
    document.querySelector('form.auth-form').submit();
    return true;
  })()`);
  await sleep(2500);
  console.log('[LOGIN-URL]', await evalJS('location.href'));

  // --- VERIFY SURAH PAGE ---
  console.log('\n===== SURAH PAGE =====');
  await cdp.send('Page.navigate', { url: BASE + '/quran/surah/1' });
  await sleep(3500);
  console.log('[SURAH-URL]', await evalJS('location.href'));

  // Check the 3D player DOM structure
  const surahCheck = await evalJS(`(function(){
    const player = document.getElementById('audio-player');
    const visual = document.getElementById('audio-player-visual');
    const core = document.getElementById('audio-player-icon-wrap');
    const rings = document.querySelectorAll('.play-ring');
    const waveform = document.getElementById('audio-waveform');
    const waveformBars = document.querySelectorAll('.audio-waveform span');
    const progress = document.getElementById('audio-progress');
    const progressFill = document.getElementById('audio-progress-fill');
    const speedBtn = document.getElementById('audio-speed-btn');
    const repeatBtn = document.getElementById('audio-repeat-btn');
    const audioBtns = document.querySelectorAll('.audio-btn').length;
    const nativeInputs = document.querySelectorAll('#audio-player input[type="range"]').length;
    const nativeSelects = document.querySelectorAll('#audio-player select').length;
    const playerStyle = player ? getComputedStyle(player) : null;
    return {
      playerExists: !!player,
      visualExists: !!visual,
      coreExists: !!core,
      ringCount: rings.length,
      waveformExists: !!waveform,
      waveformBarCount: waveformBars.length,
      progressExists: !!progress,
      progressFillExists: !!progressFill,
      speedBtnExists: !!speedBtn,
      repeatBtnExists: !!repeatBtn,
      audioBtnCount: audioBtns,
      nativeInputCount: nativeInputs,
      nativeSelectCount: nativeSelects,
      playerPerspective: playerStyle ? playerStyle.perspective : 'N/A',
      playerTransformStyle: playerStyle ? playerStyle.transformStyle : 'N/A'
    };
  })()`);
  console.log('[SURAH-3D-DOM]', JSON.stringify(surahCheck, null, 2));

  // Click the first ayah play button
  console.log('\n--- Clicking play on Ayah 1 ---');
  await evalJS(`document.querySelector('.audio-btn').click(); true`);
  await sleep(3500);

  const surahPlaying = await evalJS(`(function(){
    const player = document.getElementById('audio-player');
    const icon = document.getElementById('audio-player-icon');
    const waveform = document.getElementById('audio-waveform');
    const display = player ? player.style.display : 'none';
    return {
      playerDisplay: display,
      playerHasPlayingClass: player ? player.classList.contains('is-playing') : false,
      iconClass: icon ? icon.className : 'NONE',
      waveformOpacity: waveform ? getComputedStyle(waveform).opacity : 'N/A',
      firstAyahHasPlaying: !!document.querySelector('.ayah-item.playing'),
      activeBtnIcon: document.querySelector('.ayah-item.playing .audio-btn i') ? document.querySelector('.ayah-item.playing .audio-btn i').className : 'NONE',
      eqBarsCount: document.querySelectorAll('.ayah-item.playing .audio-equalizer span').length,
      progressFillWidth: document.getElementById('audio-progress-fill') ? document.getElementById('audio-progress-fill').style.width : 'N/A'
    };
  })()`);
  console.log('[SURAH-PLAYING-STATE]', JSON.stringify(surahPlaying, null, 2));

  // Click pause on the sticky player play/pause button
  await evalJS(`document.getElementById('audio-play-pause').click(); true`);
  await sleep(1200);
  const surahPaused = await evalJS(`(function(){
    const icon = document.getElementById('audio-player-icon');
    return {
      iconClass: icon ? icon.className : 'NONE',
      playerHasPlayingClass: document.getElementById('audio-player').classList.contains('is-playing')
    };
  })()`);
  console.log('[SURAH-PAUSED-STATE]', JSON.stringify(surahPaused, null, 2));

  // --- VERIFY PARA PAGE ---
  console.log('\n===== PARA PAGE =====');
  await cdp.send('Page.navigate', { url: BASE + '/quran/para/1' });
  await sleep(3500);
  console.log('[PARA-URL]', await evalJS('location.href'));

  const paraCheck = await evalJS(`(function(){
    const player = document.getElementById('audio-player');
    const visual = document.getElementById('audio-player-visual');
    const rings = document.querySelectorAll('.play-ring');
    const waveform = document.getElementById('audio-waveform');
    const waveformBars = document.querySelectorAll('.audio-waveform span');
    const audioBtns = document.querySelectorAll('.audio-btn').length;
    const nativeInputs = document.querySelectorAll('#audio-player input[type="range"]').length;
    const nativeSelects = document.querySelectorAll('#audio-player select').length;
    return {
      playerExists: !!player,
      visualExists: !!visual,
      ringCount: rings.length,
      waveformExists: !!waveform,
      waveformBarCount: waveformBars.length,
      audioBtnCount: audioBtns,
      nativeInputCount: nativeInputs,
      nativeSelectCount: nativeSelects
    };
  })()`);
  console.log('[PARA-3D-DOM]', JSON.stringify(paraCheck, null, 2));

  // Click first audio button
  await evalJS(`document.querySelector('.audio-btn').click(); true`);
  await sleep(3500);
  const paraPlaying = await evalJS(`(function(){
    const player = document.getElementById('audio-player');
    const icon = document.getElementById('audio-player-icon');
    const waveform = document.getElementById('audio-waveform');
    return {
      playerDisplay: player ? player.style.display : 'none',
      playerHasPlayingClass: player ? player.classList.contains('is-playing') : false,
      iconClass: icon ? icon.className : 'NONE',
      waveformOpacity: waveform ? getComputedStyle(waveform).opacity : 'N/A',
      firstAyahHasPlaying: !!document.querySelector('.ayah-item.playing'),
      activeBtnIcon: document.querySelector('.ayah-item.playing .audio-btn i') ? document.querySelector('.ayah-item.playing .audio-btn i').className : 'NONE'
    };
  })()`);
  console.log('[PARA-PLAYING-STATE]', JSON.stringify(paraPlaying, null, 2));

  // --- Console errors summary ---
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