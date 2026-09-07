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
  assert.match(helpers, /senderNumber,\n\s+senderPhone,/);
  assert.match(helpers, /senderId,\n\s+\.\.\.\(senderPhone \? \{ senderPhone \} : \{\}\),/);
  assert.deepEqual(verifyBridgeContents(bridge, helpers), { ok: true });
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
