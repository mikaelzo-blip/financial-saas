import assert from 'node:assert/strict';
import test from 'node:test';

import {
  patchBridgeHelpersContent,
  patchBridgeScriptContent,
  verifyBridgeContents,
} from '../verify_and_patch_baileys_bridge.mjs';

const bridgeSource = String.raw`
// Build LID → phone reverse map from session files (lid-mapping-{phone}.json)
function buildLidMap() {
  const map = {};
  try {
    for (const f of readdirSync(SESSION_DIR)) {
      const m = f.match(/^lid-mapping-(\d+)\.json$/);
      if (!m) continue;
      const phone = m[1];
      const lid = JSON.parse(readFileSync(path.join(SESSION_DIR, f), 'utf8'));
      if (lid) map[String(lid)] = phone;
    }
  } catch {}
  return map;
}
let lidToPhone = buildLidMap();

function enqueuePollUpdateEvent({ key }) {
  const senderId = normalizeWhatsAppId(key?.participant || '');
  const event = {
    messageId: 'poll',
    chatId,
    senderId,
  };
  return event;
}

async function startSocket() {
  const senderId = msg.key.participant || chatId;
  const isGroup = chatId.endsWith('@g.us');
  const senderNumber = senderId.replace(/@.*/, '');
  emitDebugEvent({
    senderId,
  });
  const event = await extractBridgeEvent({
    msg,
    chatId,
    senderId,
    senderNumber,
    botIds,
    isGroup,
  });
}
`;

const helpersSource = String.raw`
export async function extractBridgeEvent({
  msg,
  chatId,
  senderId,
  senderNumber,
  botIds = [],
}) {
  return {
    messageId: msg.key.id,
    chatId,
    senderId,
    senderName: msg.pushName || senderNumber,
  };
}
`;

test('patches current Hermes bridge for canonical senderPhone resolution', () => {
  const bridge = patchBridgeScriptContent(bridgeSource);
  const helpers = patchBridgeHelpersContent(helpersSource);

  assert.match(bridge, /mReverse/);
  assert.match(bridge, /function resolveSenderPhone/);
  assert.equal((bridge.match(/const senderPhone = resolveSenderPhone/g) || []).length, 2);
  assert.match(bridge, /senderNumber,\n\s+senderPhone,/);
  assert.match(bridge, /lid-mapping-\$\{senderNumber\}_reverse\.json/);
  assert.match(helpers, /senderNumber,\n\s+senderPhone,/);
  assert.match(helpers, /senderId,\n\s+\.\.\.\(senderPhone \? \{ senderPhone \} : \{\}\),/);
  assert.deepEqual(verifyBridgeContents(bridge, helpers), { ok: true });
});

test('upgrades legacy v1 patched bridge to canonical resilient resolver', () => {
  const legacyBridge = bridgeSource.replace(
    `// Build LID → phone reverse map from session files (lid-mapping-{phone}.json)
function buildLidMap() {
  const map = {};
  try {
    for (const f of readdirSync(SESSION_DIR)) {
      const m = f.match(/^lid-mapping-(\\d+)\\.json$/);
      if (!m) continue;
      const phone = m[1];
      const lid = JSON.parse(readFileSync(path.join(SESSION_DIR, f), 'utf8'));
      if (lid) map[String(lid)] = phone;
    }
  } catch {}
  return map;
}
let lidToPhone = buildLidMap();`,
    `// Build LID → phone reverse map from both Hermes mapping file formats.
function buildLidMap() {
  const map = {};
  try {
    for (const f of readdirSync(SESSION_DIR)) {
      const mPhone = f.match(/^lid-mapping-(\\d+)\\.json$/);
      if (mPhone) {
        const phone = mPhone[1];
        const lid = JSON.parse(readFileSync(path.join(SESSION_DIR, f), 'utf8'));
        if (lid) map[String(lid)] = phone;
        continue;
      }
      const mReverse = f.match(/^lid-mapping-(\\d+)_reverse\\.json$/);
      if (mReverse) {
        const lid = mReverse[1];
        const phone = JSON.parse(readFileSync(path.join(SESSION_DIR, f), 'utf8'));
        if (phone) map[String(lid)] = String(phone);
      }
    }
  } catch {}
  return map;
}
let lidToPhone = buildLidMap();

function resolveSenderPhone(senderId, senderNumber) {
  if (senderId.endsWith('@s.whatsapp.net')) {
    const raw = senderNumber.replace(/^\\+/, '');
    return /^\\d+$/.test(raw) ? raw : undefined;
  }
  if (senderId.endsWith('@lid')) {
    const mapped = lidToPhone[senderNumber];
    if (!mapped) return undefined;
    const raw = String(mapped).replace(/^\\+/, '');
    return /^\\d+$/.test(raw) ? raw : undefined;
  }
  return undefined;
}`,
  );

  const upgraded = patchBridgeScriptContent(legacyBridge);
  assert.match(upgraded, /lid-mapping-\$\{senderNumber\}_reverse\.json/);
  assert.match(upgraded, /function resolveSenderPhone/);
});

test('patch is idempotent', () => {
  const bridge = patchBridgeScriptContent(bridgeSource);
  const helpers = patchBridgeHelpersContent(helpersSource);

  assert.equal(patchBridgeScriptContent(bridge), bridge);
  assert.equal(patchBridgeHelpersContent(helpers), helpers);
});

test('fails closed when upstream bridge shape is unknown', () => {
  assert.throws(() => patchBridgeScriptContent('console.log("new upstream");'), /unsupported Hermes bridge version/);
  assert.throws(() => patchBridgeHelpersContent('export const changed = true;'), /unsupported Hermes bridge version/);
});
