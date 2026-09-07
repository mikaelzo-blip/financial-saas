import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8');

test('one-click lifecycle includes configured local Baileys', () => {
  const start = read('scripts/windows/Start-Financial-SaaS.ps1');
  const stop = read('scripts/windows/Stop-Financial-SaaS.ps1');

  assert.match(start, /WHATSAPP_PROVIDER.*baileys/);
  assert.match(start, /verify_and_patch_baileys_bridge\.mjs/);
  assert.match(start, /export_whatsapp_allowlist\.py/);
  assert.match(start, /127\.0\.0\.1:\$BridgePort\/health/);
  assert.match(start, /status -ne 'connected'/);
  assert.match(stop, /Name = 'baileys'/);
});

test('release artifacts consistently defer PC-off capture', () => {
  const tracker = read('docs/RC1_IMPLEMENTATION_TRACKER.md');
  const status = read('PROJECT_STATUS.md');
  const spec = read('specs/007-whatsapp-integration/spec.md');
  const decision = read('docs/decisions/ADR-2026-09-07-rc1-local-first-whatsapp.md');

  for (const artifact of [tracker, status, spec, decision]) {
    assert.match(artifact, /DEFERRED_POST_RC1/);
    assert.match(artifact, /LOCAL-FIRST|local-first/i);
  }
  assert.doesNotMatch(status, /R1: Durable PC-off capture complete/);
});

test('future relay components remain preserved', () => {
  for (const relativePath of [
    'edge-relay/src/index.ts',
    'edge-relay/schema.sql',
    'backend/src/services/remote_inbox_client.py',
    'backend/src/services/remote_relay_emulator.py',
  ]) {
    assert.ok(fs.existsSync(path.join(root, relativePath)), `${relativePath} must remain`);
  }
});
