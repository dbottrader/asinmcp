// True AI Phone PWA — portal client for device_agent.py, v0.1.
// No build chain, no dependencies. WebCrypto Ed25519 for signing.
// Private key is stored in this browser's localStorage as JWK —
// honest limit: fine for a test device, NOT a production secret store.
const $ = id => document.getElementById(id);
const enc = new TextEncoder();
const hex = buf => [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
const sortedStringify = obj => {
  if (obj === null || typeof obj !== 'object') return JSON.stringify(obj);
  if (Array.isArray(obj)) return '[' + obj.map(sortedStringify).join(',') + ']';
  return '{' + Object.keys(obj).sort().map(k => JSON.stringify(k) + ':' + sortedStringify(obj[k])).join(',') + '}';
};
const base = () => $('base').value.replace(/\/$/, '');
async function req(path, body) {
  const r = await fetch(base() + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const t = await r.text();
  try { return {status: r.status, json: JSON.parse(t)}; } catch { return {status: r.status, text: t}; }
}
async function loadKey() {
  const jwk = localStorage.getItem('dp-agent-jwk');
  if (!jwk) return null;
  return crypto.subtle.importKey('jwk', JSON.parse(jwk), {name: 'Ed25519'}, true, ['sign']);
}
$('btnKeygen').onclick = async () => {
  try {
    if (!crypto.subtle || !crypto.subtle.generateKey) throw new Error('WebCrypto Ed25519 not available in this browser');
    const kp = await crypto.subtle.generateKey({name: 'Ed25519'}, true, ['sign', 'verify']);
    const priv = await crypto.subtle.exportKey('jwk', kp.privateKey);
    const pub = await crypto.subtle.exportKey('raw', kp.publicKey);
    localStorage.setItem('dp-agent-jwk', JSON.stringify(priv));
    $('pubkey').value = hex(pub);
    $('pairOut').textContent = 'Key generated. Public key above — pair it with the device, then send signed commands. Private key stays in this browser.';
  } catch (e) { $('pairOut').textContent = 'Key generation failed: ' + e.message + '\nFallback: run portal_client.py keygen on a computer and paste its public key logic there; this browser cannot sign.'; }
};
$('btnStatus').onclick = async () => {
  try { const r = await req('/status'); $('statusOut').textContent = JSON.stringify(r.json ?? r, null, 2); }
  catch (e) { $('statusOut').textContent = 'Status failed: ' + e.message; }
};
$('btnPair').onclick = async () => {
  const pub = $('pubkey').value.trim();
  if (!pub) return $('pairOut').textContent = 'Generate an agent key first.';
  try {
    const r = await req('/pair', {agent_name: $('agentName').value.trim(), agent_pubkey: pub, pairing_code: $('pairCode').value.trim()});
    $('pairOut').textContent = JSON.stringify(r.json ?? r, null, 2);
  } catch (e) { $('pairOut').textContent = 'Pair failed: ' + e.message; }
};
function buildArgs() {
  const action = $('action').value;
  const args = {path: $('path').value.trim()};
  if (action === 'exec_safe') { args.cmd = $('path').value.trim(); delete args.path; args.args = []; }
  if (action === 'write_file') args.content = $('content').value;
  return {action, args};
}
function commandHash(action, args) {
  // Must match device_agent.py: sha256 over canonical JSON of {action, args}
  return crypto.subtle.digest('SHA-256', enc.encode(sortedStringify({action, args}))).then(h => hex(h));
}
$('btnHash').onclick = async () => {
  const {action, args} = buildArgs();
  $('cmdOut').textContent = 'Command hash (give this exact hash to the device owner for approval):\n' + await commandHash(action, args);
};
$('btnCmd').onclick = async () => {
  try {
    const key = await loadKey();
    if (!key) return $('cmdOut').textContent = 'Generate an agent key first.';
    const pub = $('pubkey').value.trim();
    const {action, args} = buildArgs();
    const ts = Math.floor(Date.now() / 1000);
    const nonce = hex(crypto.getRandomValues(new Uint8Array(8)));
    const msg = `device-portal/v1|${pub}|${ts}|${nonce}|${action}|${sortedStringify(args)}`;
    const sig = await crypto.subtle.sign({name: 'Ed25519'}, key, enc.encode(msg));
    const body = {agent: $('agentName').value.trim(), ts, nonce, action, args, signature: hex(sig)};
    const tok = $('token').value.trim();
    if (tok) body.approval_token = tok;
    const r = await req('/command', body);
    $('cmdOut').textContent = JSON.stringify(r.json ?? r, null, 2);
  } catch (e) { $('cmdOut').textContent = 'Command failed: ' + e.message; }
};
$('btnAudit').onclick = async () => {
  try { const r = await req('/audit'); $('auditOut').textContent = JSON.stringify(r.json ?? r, null, 2); }
  catch (e) { $('auditOut').textContent = 'Audit failed: ' + e.message; }
};
$('btnKill').onclick = async () => {
  if (!confirm('Kill switch: revoke all agent keys and stop the device agent?')) return;
  try { const r = await req('/kill', {}); $('statusOut').textContent = JSON.stringify(r.json ?? r, null, 2); }
  catch (e) { $('statusOut').textContent = 'Kill failed: ' + e.message; }
};
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}
