#!/usr/bin/env node
/**
 * Verify and, when necessary, patch the installed Hermes Baileys bridge so
 * WhatsApp LIDs are resolved to canonical phone numbers at the transport edge.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);

function replaceRequired(content, before, after, label) {
  if (content.includes(after)) return content;
  if (!content.includes(before)) {
    throw new Error(`Cannot patch ${label}: unsupported Hermes bridge version.`);
  }
  return content.replace(before, after);
}

export function resolveBridgeScriptPath() {
  const custom = process.env.WHATSAPP_BRIDGE_SCRIPT;
  if (custom && fs.existsSync(custom)) return custom;

  const appData = process.env.LOCALAPPDATA
    || (process.env.USERPROFILE ? path.join(process.env.USERPROFILE, 'AppData', 'Local') : '');
  const candidates = [
    path.join(appData, 'hermes', 'hermes-agent', 'scripts', 'whatsapp-bridge', 'bridge.js'),
    path.join(process.env.USERPROFILE || '', '.hermes', 'scripts', 'whatsapp-bridge', 'bridge.js'),
    path.join(process.env.HOME || '', '.hermes', 'scripts', 'whatsapp-bridge', 'bridge.js'),
  ];
  return candidates.find((candidate) => candidate && fs.existsSync(candidate)) || null;
}

export function patchBridgeScriptContent(source) {
  let content = source;

  content = replaceRequired(
    content,
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
    'LID resolver',
  );

  const pollSenderMarker = "  const senderPhone = resolveSenderPhone(senderId, senderNumber);\n  const event = {";
  if (!content.includes(pollSenderMarker)) {
    const pollEventMatch = content.match(/(  const event = \{\n    messageId: [^\n]+\n    chatId,\n    senderId,)/);
    if (!pollEventMatch) {
      throw new Error('Cannot patch poll sender normalization: unsupported Hermes bridge version.');
    }
    content = content.replace(
      pollEventMatch[1],
      `  const senderNumber = senderId.replace(/@.*/, '');\n  const senderPhone = resolveSenderPhone(senderId, senderNumber);\n${pollEventMatch[1].replace('    senderId,', '    senderId,\n    ...(senderPhone ? { senderPhone } : {}),')}`,
    );
  }

  const senderMatches = [...content.matchAll(/^(\s+)const senderNumber = senderId\.replace\(\/@\.\*\/, ''\);$/gm)];
  const messageSenderMatch = senderMatches.at(-1);
  if (!messageSenderMatch || messageSenderMatch.index === undefined) {
    throw new Error('Cannot patch message sender normalization: unsupported Hermes bridge version.');
  }
  const insertionPoint = messageSenderMatch.index + messageSenderMatch[0].length;
  const messageSenderPhone = `\n${messageSenderMatch[1]}const senderPhone = resolveSenderPhone(senderId, senderNumber);`;
  if (!content.startsWith(messageSenderPhone, insertionPoint)) {
    content = `${content.slice(0, insertionPoint)}${messageSenderPhone}${content.slice(insertionPoint)}`;
  }

  if (!content.match(/senderNumber,\n\s+senderPhone,\n\s+botIds,/)) {
    const forwarded = content.replace(
      /(senderId,\n(\s+)senderNumber,\n)\2botIds,/,
      '$1$2senderPhone,\n$2botIds,',
    );
    if (forwarded === content) {
      throw new Error('Cannot patch senderPhone forwarding: unsupported Hermes bridge version.');
    }
    content = forwarded;
  }

  return content;
}

export function patchBridgeHelpersContent(source) {
  let content = source;
  content = replaceRequired(
    content,
    `  senderId,
  senderNumber,
  botIds = [],`,
    `  senderId,
  senderNumber,
  senderPhone,
  botIds = [],`,
    'bridge helper parameters',
  );
  content = replaceRequired(
    content,
    `    chatId,
    senderId,
    senderName:`,
    `    chatId,
    senderId,
    ...(senderPhone ? { senderPhone } : {}),
    senderName:`,
    'bridge helper event',
  );
  return content;
}

export function verifyBridgeContents(bridgeContent, helpersContent) {
  const checks = [
    bridgeContent.includes('mReverse'),
    bridgeContent.includes('function resolveSenderPhone'),
    bridgeContent.includes('const senderPhone = resolveSenderPhone'),
    /senderNumber,\n\s+senderPhone,/.test(bridgeContent),
    helpersContent.includes('senderNumber,\n  senderPhone,'),
    helpersContent.includes('...(senderPhone ? { senderPhone } : {}),'),
  ];
  return checks.every(Boolean)
    ? { ok: true }
    : { ok: false, reason: 'Bridge is missing canonical senderPhone resolution.' };
}

export function verifyBridgeScript(scriptPath) {
  if (!scriptPath || !fs.existsSync(scriptPath)) {
    return { ok: false, reason: `Bridge script not found at ${scriptPath || '(unknown)'}` };
  }
  const helpersPath = path.join(path.dirname(scriptPath), 'bridge_helpers.js');
  if (!fs.existsSync(helpersPath)) {
    return { ok: false, reason: `Bridge helper not found at ${helpersPath}` };
  }
  return verifyBridgeContents(
    fs.readFileSync(scriptPath, 'utf8'),
    fs.readFileSync(helpersPath, 'utf8'),
  );
}

export function reapplyBridgePatch(scriptPath) {
  const helpersPath = path.join(path.dirname(scriptPath), 'bridge_helpers.js');
  if (!fs.existsSync(helpersPath)) {
    throw new Error(`Bridge helper not found at ${helpersPath}`);
  }

  const originalBridge = fs.readFileSync(scriptPath, 'utf8');
  const originalHelpers = fs.readFileSync(helpersPath, 'utf8');
  const patchedBridge = patchBridgeScriptContent(originalBridge);
  const patchedHelpers = patchBridgeHelpersContent(originalHelpers);
  const status = verifyBridgeContents(patchedBridge, patchedHelpers);
  if (!status.ok) throw new Error(status.reason);

  try {
    if (patchedBridge !== originalBridge) fs.writeFileSync(scriptPath, patchedBridge, 'utf8');
    if (patchedHelpers !== originalHelpers) fs.writeFileSync(helpersPath, patchedHelpers, 'utf8');
  } catch (error) {
    fs.writeFileSync(scriptPath, originalBridge, 'utf8');
    fs.writeFileSync(helpersPath, originalHelpers, 'utf8');
    throw error;
  }

  return {
    ok: true,
    changed: patchedBridge !== originalBridge || patchedHelpers !== originalHelpers,
  };
}

if (process.argv[1] && path.resolve(process.argv[1]) === __filename) {
  const scriptPath = resolveBridgeScriptPath();
  if (!scriptPath) {
    console.error('ERROR: Could not locate Hermes Baileys bridge.js');
    process.exit(1);
  }
  try {
    const result = reapplyBridgePatch(scriptPath);
    console.log(`${result.changed ? 'PATCHED' : 'PASS'}: Bridge verified at ${scriptPath}`);
  } catch (error) {
    console.error(`VERIFICATION FAILED: ${error.message}`);
    process.exit(1);
  }
}
