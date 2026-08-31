# Implementation Plan: Dependency Security Gates

## Constitution check

PASS. This is CI and dependency maintenance only. No financial domain behavior changes.

## Plan

1. Reproduce backend and frontend audits from committed lockfiles.
2. Remove or upgrade vulnerable transitive packages without adding unnecessary abstractions.
3. Add pinned, lockfile-based audit commands to existing CI jobs.
4. Document local reproduction and update readiness/status evidence.
5. Run locked sync, audits, full tests, migrations, frontend gates, repository safety, and final consistency analysis.

## Technical decision

`python-jose[cryptography]` pulls vulnerable `ecdsa`, while this repository signs only HS256 JWTs. Remove the unused `ecdsa` dependency path by replacing `python-jose` with the already-standard `PyJWT` library using the existing HMAC API boundary. This is the smallest dependency correction that preserves behavior and eliminates the advisory without an ignore.
