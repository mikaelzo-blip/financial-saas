# Research: Document Intelligence & Financial Document Intake

## Provider boundary

**Decision**: Define an async provider protocol returning strict provider-neutral evidence. Ship a local adapter for supported PDFs/images and a deterministic scripted adapter for tests; select through configuration/factory injection.

**Rationale**: Preserves replaceability, permits credential-free development, and prevents vendor response shapes from entering domain/accounting code.

**Alternatives considered**: Direct cloud OCR requires credentials and creates coupling. Provider calls inside routes harm testability and retries.

## Persisted pipeline state

**Decision**: Persist processing status, provider/version, attempt count, structured extraction, matches, confidence, candidate, flags, failure details, and timestamps on Document; persist reviewer corrections as append-only events.

**Rationale**: Durable state supports retries, observability, audit reconstruction, and a future queue worker without changing contracts.

**Alternatives considered**: In-memory jobs lose state. A distributed queue is unnecessary for this MVP.

## Strict evidence schema

**Decision**: Use nested Pydantic schemas with `Decimal` money and explicit evidence metadata. Unknown fields remain null; malformed/extra provider values fail validation.

**Rationale**: Enforces evidence grounding and prevents free text or binary floats becoming authoritative financial data.

**Alternatives considered**: Schemaless JSON violates FR-008/SC-003. A single confidence score violates the multi-dimensional requirement.

## Matching and confidence

**Decision**: Apply exact identifiers first, normalized exact names second, conservative fuzzy matching last. Only unique matches meeting threshold are proposed. Critical confidence below 0.85 or ambiguous/no matches add flags.

**Rationale**: Deterministic evidence outranks similarity; ambiguity must not silently select financial dimensions.

**Alternatives considered**: First fuzzy hit creates false matches. Automatic master creation violates FR-013.

## Candidate/accounting boundary

**Decision**: Store a proposal with transaction type, matched IDs, category, dates, Decimal amounts, and evidence links. Approval invokes existing transaction intake; the document module never creates journal lines.

**Rationale**: Implements Single Input while retaining posting rules as sole accounting authority.

**Alternatives considered**: Provider-generated journals and direct posting are Constitution violations.

## Duplicate semantics

**Decision**: Reject exact tenant SHA-256 matches before extraction. Flag suspected business duplicates using reference+counterparty or exact amount+counterparty within ±1 day; do not discard them.

**Rationale**: Binary identity differs from economic similarity; legitimate repetitions require review.

**Alternatives considered**: Cross-tenant checks leak tenant existence. Automatic suppression may discard legitimate events.

## File security

**Decision**: Enforce a 25 MB streaming limit, declared MIME allowlist plus content signatures, generated storage names, PDF encryption detection, and resolved paths inside tenant storage. Expose no update/delete API.

**Rationale**: Filenames and declared MIME are untrusted; confidentiality and immutability are mandatory.

**Alternatives considered**: Trusting extensions/content type alone fails closed security. Virus scanning stays an adapter boundary until an approved scanner exists.
