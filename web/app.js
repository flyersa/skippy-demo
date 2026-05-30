/* Skippy demo PWA — public, English, push-to-talk. No login, no cards.
 * Device identity via OverpoweredJS clusterUUID when an API key is configured
 * (window.OPJS_API_KEY), else a stable localStorage UUID. The device id is
 * sent as X-Device-Id so the brain keeps each visitor's conversation separate.
 */
'use strict';

const charVideo = document.getElementById('char-video');
const statePill = document.getElementById('state-pill');
const captionWrap = document.getElementById('caption');
const capYou = document.getElementById('caption-you');
const capSkippy = document.getElementById('caption-skippy');
const talkBtn = document.getElementById('talk-btn');
const talkLabel = document.getElementById('talk-label');
const talkHint = document.getElementById('talk-hint');
const stopBtn = document.getElementById('stop-btn');
function _dismissHint() { if (talkHint) talkHint.classList.add('gone'); talkBtn.classList.remove('hint-pulse'); }
const textBtn = document.getElementById('text-btn');
const textSheet = document.getElementById('text-sheet');
const textInput = document.getElementById('text-input');
const textSend = document.getElementById('text-send');
const textCancel = document.getElementById('text-cancel');
const body = document.body;

// ===== device identity =====
function _uuid() {
  if (crypto && crypto.randomUUID) return crypto.randomUUID();
  return 'd-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
}
let DEVICE_ID = localStorage.getItem('skippy_dev') || _uuid();
localStorage.setItem('skippy_dev', DEVICE_ID);

// ===== clips / state =====
const CLIPS = { active: 'clips/idle.mp4', listening: 'clips/skippy_curious.mp4',
                thinking: 'clips/thinking.mp4', speaking: 'clips/speaking.mp4' };
const ACTIVE_CLIP_POOL = [
  'clips/idle.mp4', 'clips/idle.mp4', 'clips/idle.mp4', 'clips/idle.mp4',
  'clips/idle_starry_calm_01.mp4', 'clips/idle_room_drift_01.mp4',
  'clips/idle_console_01.mp4', 'clips/idle_yawning_01.mp4',
  'clips/idle_gizmo_napping_01.mp4', 'clips/skippy_feeding_gizmo.mp4',
  'clips/skippy_stargazing.mp4', 'clips/skippy_petting_pug.mp4',
  'clips/idle_pokemon_01.mp4',
];
const THINKING_CLIP_POOL = ['clips/thinking.mp4', 'clips/thinking-2.mp4', 'clips/thinking-3.mp4'];
const STATE_LABEL = { active: 'ready', listening: 'listening…', thinking: 'thinking…', speaking: 'speaking' };

let currentState = 'active';
charVideo.loop = false;

function loadVisualFor(state) {
  let src;
  if (state === 'active') src = ACTIVE_CLIP_POOL[Math.floor(Math.random() * ACTIVE_CLIP_POOL.length)];
  else if (state === 'thinking') src = THINKING_CLIP_POOL[Math.floor(Math.random() * THINKING_CLIP_POOL.length)];
  else src = CLIPS[state] || CLIPS.active;
  if (charVideo.getAttribute('src') !== src) {
    charVideo.style.opacity = '0';
    charVideo.src = src;
    const onReady = () => { charVideo.removeEventListener('loadeddata', onReady); charVideo.style.opacity = '1'; };
    charVideo.addEventListener('loadeddata', onReady);
    const p = charVideo.play(); if (p && p.catch) p.catch(() => {});
  } else if (charVideo.paused) { charVideo.play().catch(() => {}); }
}
function setState(name) {
  if (!STATE_LABEL[name]) return;
  if (currentState === name) return;
  body.classList.remove('state-' + currentState);
  body.classList.add('state-' + name);
  currentState = name;
  statePill.textContent = STATE_LABEL[name];
  stopBtn.classList.toggle('hidden', name !== 'speaking');
  loadVisualFor(name);
}
charVideo.addEventListener('ended', () => {
  if (currentState === 'active') {
    const next = ACTIVE_CLIP_POOL[Math.floor(Math.random() * ACTIVE_CLIP_POOL.length)];
    charVideo.style.opacity = '0'; charVideo.src = next;
    const onReady = () => { charVideo.removeEventListener('loadeddata', onReady); charVideo.style.opacity = '1'; };
    charVideo.addEventListener('loadeddata', onReady); charVideo.play().catch(() => {});
  } else { charVideo.currentTime = 0; charVideo.play().catch(() => {}); }
});

// ===== captions (auto-fade) =====
function showCaption(you, skippy) {
  capYou.textContent = you || ''; capSkippy.textContent = skippy || '';
  capYou.style.display = you ? 'block' : 'none';
  capSkippy.style.display = skippy ? 'block' : 'none';
  captionWrap.classList.toggle('hidden', !you && !skippy);
}
function hideCaption() { captionWrap.classList.add('hidden'); }
let _idleClear = null;
function cancelIdleClear() { if (_idleClear) { clearTimeout(_idleClear); _idleClear = null; } }
function scheduleIdleClear() {
  cancelIdleClear();
  _idleClear = setTimeout(() => {
    captionWrap.classList.add('fade-out');
    setTimeout(() => { hideCaption(); captionWrap.classList.remove('fade-out'); }, 650);
  }, 10000);
}

// ===== header decode + audio (L16 24k stream) =====
function decodeHeader(v) { if (!v) return ''; try { return new TextDecoder().decode(Uint8Array.from(atob(v), c => c.charCodeAt(0))); } catch { return ''; } }
const SAMPLE_RATE = 24000;
let audioCtx = null, _audioPrimed = false;
function ensureAudio() {
  // iOS Safari rejects a forced sampleRate and is strict about unlocking the
  // context inside a user gesture. Use the device-native rate (the 24 kHz PCM
  // buffers below are resampled to it by the Web Audio API), resume on gesture,
  // and prime with a silent buffer to fully unlock playback on iOS.
  if (!audioCtx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AC();
  }
  if (audioCtx.state === 'suspended') audioCtx.resume();
  if (!_audioPrimed) {
    try {
      const b = audioCtx.createBuffer(1, 1, audioCtx.sampleRate);
      const s = audioCtx.createBufferSource();
      s.buffer = b; s.connect(audioCtx.destination); s.start(0);
      _audioPrimed = true;
    } catch (e) {}
  }
  return audioCtx;
}
let _sources = [];
function _stopAll() { _sources.forEach(s => { try { s.stop(); } catch {} }); _sources = []; }
async function streamReply(resp) {
  const ctx = ensureAudio();
  let until = ctx.currentTime + 0.08, carry = new Uint8Array(0), first = true;
  _sources = [];
  const reader = resp.body.getReader();
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    let buf;
    if (carry.length) { buf = new Uint8Array(carry.length + value.length); buf.set(carry, 0); buf.set(value, carry.length); }
    else buf = value;
    const even = buf.length & ~1;
    if (even < buf.length) { carry = buf.slice(even); buf = buf.slice(0, even); } else carry = new Uint8Array(0);
    if (!buf.length) continue;
    if (first) { stopBridge(); first = false; }   // cut filler exactly when real audio starts
    const i16 = new Int16Array(buf.buffer, buf.byteOffset, buf.length / 2);
    const f32 = new Float32Array(i16.length);
    for (let i = 0; i < i16.length; i++) f32[i] = i16[i] / 32768;
    const ab = ctx.createBuffer(1, f32.length, SAMPLE_RATE);
    ab.copyToChannel(f32, 0);
    const s = ctx.createBufferSource(); s.buffer = ab; s.connect(ctx.destination);
    const at = Math.max(until, ctx.currentTime + 0.02);
    s.start(at); _sources.push(s);
    until = at + (f32.length / SAMPLE_RATE);
  }
  await new Promise(r => setTimeout(r, Math.max(0, (until - ctx.currentTime) * 1000) + 120));
}

// ===== bridge phrases (play instantly to mask LLM+TTS latency) =====
// Decoded into AudioBuffers and played through the SAME unlocked AudioContext
// as the reply — a bare new Audio().play() gets blocked by autoplay policy.
let _bridgeBuffers = [];
let _bridgeNode = null;
let _bridgesLoading = false;
async function ensureBridges() {
  if (_bridgesLoading || _bridgeBuffers.length) return;
  _bridgesLoading = true;
  try {
    const ctx = ensureAudio();
    const list = ((await (await fetch('/api/bridges')).json()).bridges) || [];
    for (const name of list) {
      try {
        const ab = await (await fetch('/bridges/' + encodeURIComponent(name))).arrayBuffer();
        _bridgeBuffers.push(await ctx.decodeAudioData(ab));
      } catch (e) { /* skip a bad one */ }
    }
  } catch (e) { _bridgesLoading = false; }
}
function playBridge() {
  if (!_bridgeBuffers.length || !audioCtx) return;
  try {
    const buf = _bridgeBuffers[Math.floor(Math.random() * _bridgeBuffers.length)];
    _bridgeNode = audioCtx.createBufferSource();
    _bridgeNode.buffer = buf;
    _bridgeNode.connect(audioCtx.destination);
    _bridgeNode.start();
  } catch (e) {}
}
function stopBridge() { if (_bridgeNode) { try { _bridgeNode.stop(); } catch {} _bridgeNode = null; } }

// ===== turn =====
let _busy = false, _abort = null;
async function doTurn(kind, payload) {
  if (_busy) return;
  _busy = true; cancelIdleClear(); hideCaption(); setState('thinking');
  playBridge();
  _abort = new AbortController();
  try {
    const opts = { method: 'POST', signal: _abort.signal, headers: { 'X-Device-Id': DEVICE_ID } };
    let resp;
    if (kind === 'talk') { opts.body = payload; resp = await fetch('/api/talk', opts); }
    else { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify({ text: payload }); resp = await fetch('/api/say', opts); }
    if (!resp.ok) {
      let msg = 'Hmph. Something broke. Not my fault.';
      if (resp.status === 429) msg = 'Slow down, monkey. Even I need a breath.';
      showCaption('', msg); setState('active'); return;
    }
    const reply = decodeHeader(resp.headers.get('X-Skippy-Reply'));
    const transcript = decodeHeader(resp.headers.get('X-Skippy-Transcript'));
    showCaption(transcript, reply);
    setState('speaking');
    await streamReply(resp);   // stops the bridge on its first real audio chunk
  } catch (e) { if (e.name !== 'AbortError') console.warn('[turn]', e); }
  finally { stopBridge(); _stopAll(); _busy = false; _abort = null; setState('active'); scheduleIdleClear(); }
}
function interrupt() { if (_abort) { try { _abort.abort(); } catch {} } _stopAll(); }

// ===== push-to-talk (tap toggle) =====
let _rec = null, _chunks = [], _mic = null, _recording = false, _recTimer = null;
const MAX_REC_MS = 30000;   // hard cap: no hour-long recordings
function pickMime() {
  for (const m of ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/aac', '']) {
    if (!m || (window.MediaRecorder && MediaRecorder.isTypeSupported(m))) return m;
  }
  return '';
}
async function startRec() {
  if (_busy || _recording) return;
  _dismissHint();
  ensureAudio(); ensureBridges();
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { statePill.textContent = 'mic needs HTTPS'; return; }
  try { _mic = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch { statePill.textContent = 'mic blocked'; return; }
  _chunks = [];
  const mime = pickMime();
  try { _rec = new MediaRecorder(_mic, mime ? { mimeType: mime } : undefined); } catch { _rec = new MediaRecorder(_mic); }
  _rec.ondataavailable = e => { if (e.data && e.data.size) _chunks.push(e.data); };
  _rec.onstop = onRecStop;
  _rec.start(); _recording = true;
  _recTimer = setTimeout(() => { if (_recording) stopRec(); }, MAX_REC_MS);   // auto-send at cap
  talkBtn.classList.add('recording'); talkLabel.textContent = 'Send'; setState('listening');
}
function stopRec() {
  if (!_recording) return;
  if (_recTimer) { clearTimeout(_recTimer); _recTimer = null; }
  _recording = false; talkBtn.classList.remove('recording'); talkLabel.textContent = 'Talk';
  if (_rec && _rec.state !== 'inactive') _rec.stop();
}
function onRecStop() {
  if (_mic) { _mic.getTracks().forEach(t => t.stop()); _mic = null; }
  const blob = new Blob(_chunks, { type: (_chunks[0] && _chunks[0].type) || 'audio/webm' });
  if (blob.size < 800) { setState('active'); return; }
  doTurn('talk', blob);
}
talkBtn.addEventListener('click', () => { if (_recording) stopRec(); else if (!_busy) startRec(); });
stopBtn.addEventListener('click', interrupt);

// ===== text mode =====
textBtn.addEventListener('click', () => { textSheet.classList.remove('hidden'); textInput.focus(); });
textCancel.addEventListener('click', () => { textSheet.classList.add('hidden'); textInput.value = ''; });
function sendText() { const t = textInput.value.trim(); if (!t) return; _dismissHint(); try { ensureAudio(); ensureBridges(); } catch (e) {} textInput.value = ''; textSheet.classList.add('hidden'); doTurn('say', t); }
textSend.addEventListener('click', sendText);
textInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendText(); });

// ===== disclaimer gate (must acknowledge before using Skippy) =====
const discEl = document.getElementById('disclaimer');
const discBtn = document.getElementById('disc-accept');
if (localStorage.getItem('skippy_ack') === '1') { discEl.classList.add('hidden'); }
discBtn.addEventListener('click', () => {
  localStorage.setItem('skippy_ack', '1');
  discEl.classList.add('hidden');
  try { ensureAudio(); ensureBridges(); } catch (e) {}   // unlock audio + preload bridges on this gesture
});

// ===== boot =====
setState('active'); loadVisualFor('active');
talkBtn.classList.add('hint-pulse');
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
