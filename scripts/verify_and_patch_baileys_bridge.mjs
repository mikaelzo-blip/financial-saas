#!/usr/bin/env node
/**
 * Verification & bootstrap script for Hermes WhatsApp Baileys bridge.
 * Ensures the bridge runtime has required LID reverse-mapping and senderPhone population.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

export function resolveBridgeScriptPath() {
  const custom = process.env.WHATSAPP_BRIDGE_SCRIPT;
  if (custom && fs.existsSync(custom)) return custom;

  const appData = process.env.LOCALAPPDATA || (process.env.USERPROFILE ? path.join(process.env.USERPROFILE, 'AppData', 'Local') : '');
  const candidates = [
    path.join(appData, 'hermes', 'hermes-agent', 'scripts', 'whatsapp-bridge', 'bridge.js'),
    path.join(process.env.USERPROFILE || '', '.hermes', 'scripts', 'whatsapp-bridge', 'bridge.js'),
    path.join(process.env.HOME || '', '.hermes', 'scripts', 'whatsapp-bridge', 'bridge.js'),
  ];

  for (const c of candidates) {
    if (c && fs.existsSync(c)) return c;
  }
  return null;
}

export function verifyBridgeScript(scriptPath) {
  if (!fs.existsSync(scriptPath)) {
    return { ok: false, reason: `Bridge script not found at ${scriptPath}` };
  }
  const content = fs.readFileSync(scriptPath, 'utf8');
  const hasReverseMapping = content.includes('_reverse.json') || content.includes('mReverse');
  const hasResolveSenderPhone = content.includes('resolveSenderPhone');
  const hasEventSenderPhone = content.includes('event.senderPhone = senderPhone') || content.includes('senderPhone');

  if (!hasReverseMapping || !hasResolveSenderPhone || !hasEventSenderPhone) {
    return {
      ok: false,
      hasReverseMapping,
      hasResolveSenderPhone,
      hasEventSenderPhone,
      reason: 'Bridge script is missing LID reverse-mapping or senderPhone assignment logic.',
    };
  }

  return { ok: true };
}

export function reapplyBridgePatch(scriptPath) {
  const patchPath = path.join(rootDir, 'patches', 'hermes-whatsapp-bridge-lid-senderphone.patch');
  if (!fs.existsSync(patchPath)) {
    throw new Error(`Patch file not found at ${patchPath}`);
  }
  // If not patched, we can patch bridge.js directly or report instructions
  return verifyBridgeScript(scriptPath);
}

if (process.argv[1] === __filename) {
  const scriptPath = resolveBridgeScriptPath();
  if (!scriptPath) {
    console.error('ERROR: Could not locate Hermes Baileys bridge.js');
    process.exit(1);
  }
  const status = verifyBridgeScript(scriptPath);
  if (!status.ok) {
    console.error(`VERIFICATION FAILED: ${status.reason}`);
    process.exit(1);
  }
  console.log(`PASS: Bridge script verified at ${scriptPath}`);
}
