# Implementation Plan: AI-Assisted Management Insights & Decision Support

**Branch**: `008-ai-management-insights` | **Date**: 2026-08-30 | **Spec**: [specs/008-ai-management-insights/spec.md](file:///c:/Projects/financial-saas/specs/008-ai-management-insights/spec.md)

---

## 1. Summary

The **AI-Assisted Management Insights** feature introduces a secure, advisory intelligence layer on top of authoritative reporting APIs (Feature 004), transaction records (Feature 002), and document review stats (Feature 005). It synthesizes financial summaries, evaluates project margins, observes cash-flow runway, flags anomalous cost spikes, and powers natural language management Q&A without violating accounting invariants or accessing the database directly.

---

## 2. Technical Context

- **Language/Version**: Python >= 3.11, TypeScript / React 19 (Frontend)
- **Backend Framework**: FastAPI >= 0.115.0, SQLAlchemy 2.0 (async), Pydantic v2
- **AI Integration**: `httpx` (async client for Gemini / OpenAI / Ollama), `pydantic` JSON schema output parsing
- **Database & Storage**: PostgreSQL 16+ for `AIInsightLog` and `AIConversationSession` caching
- **Testing**: `pytest`, `pytest-asyncio`, Vitest (Frontend)
- **Target Platform**: Modular Service Layer under `backend/src/services/ai/` and API endpoints under `backend/src/api/v1/insights.py`

---

## 3. Constitution Check

*GATE: All 25 Principles from `.specify/memory/constitution.md` MUST pass.*

| Principle | Status | Alignment Rationale |
|---|---|---|
| **I. Single Input** | **PASS** | AI does not input or generate raw business events; it analyzes authoritative single entries. |
| **III. Simple User Experience** | **PASS** | Non-accountant owners/managers read clear executive narratives and plain-language answers. |
| **IV. Double-Entry Accounting** | **PASS** | AI never generates debit/credit lines or journal records. |
| **V. Deterministic Accounting Engine** | **PASS** | AI is purely advisory; deterministic backend engine remains sole accounting authority. |
| **VI. Cash Movement is Not Expense** | **PASS** | AI explicitly educates users on the difference between cash outflow and accrued expenses. |
| **VII. Source Traceability** | **PASS** | Every insight includes traceable references to authoritative reporting DTOs. |
| **VIII. Duplicate Prevention** | **PASS** | Caching prevents redundant LLM calls; AI flags duplicate trends in Review Queue. |
| **IX. Human Review for Ambiguity** | **PASS** | AI identifies ambiguous documents in Review Queue and suggests clarification without auto-posting. |
| **X. Immutable Posted Records** | **PASS** | AI cannot modify, reverse, or delete posted financial records. |
| **XI. Audit Trail** | **PASS** | All generated insights, queries, and provider latencies are logged in `AIInsightLog`. |
| **XIII. Financial Report Integrity** | **PASS** | AI consumes valid SAK reports; if `is_balanced == False`, AI reports an integrity warning. |
| **XIV. Separation of Concepts** | **PASS** | AI strictly separates Contract Value, Billed, Revenue Recognized, and Cash In/Out. |
| **XVII. Review Before Automation** | **PASS** | AI output is labeled advisory; approval remains 100% human-governed. |
| **XVIII. API Boundary** | **PASS** | AI layer calls reporting service methods; NO direct SQL queries by the LLM provider. |
| **XIX. Hermes Role** | **PASS** | Hermes can relay AI insights to WhatsApp via authenticated SaaS API. |
| **XXI. Transactional DB as Record** | **PASS** | Relational database is the sole ground truth; AI outputs are transient advisory insights. |
| **XXIII. Security & Isolation** | **PASS** | Multi-tenant filtering by `organization_id` on all data queries and cache lookups. |
| **XXIV. Testability & Verification** | **PASS** | 100% testable offline via `MockAIInsightProvider` without paid external keys. |

---

## 4. Project Structure & Module Layout

### Backend
```text
backend/src/
├── api/v1/
│   └── insights.py                    # REST API endpoints for executive summary, project insights, and Q&A
├── models/
│   └── ai_insight.py                  # SQLAlchemy models: AIInsightLog, AIConversationSession, AIConversationMessage
├── schemas/
│   └── ai_insight.py                  # Pydantic DTOs for insight payloads, Q&A queries, and grounding data
└── services/
    └── ai/
        ├── __init__.py
        ├── provider.py                # Abstract AIInsightProvider interface
        ├── mock_provider.py           # Offline mock generator for CI/CD
        ├── gemini_provider.py         # Google GenAI / Gemini client
        ├── openai_provider.py         # Universal OpenAI / Ollama client
        ├── fallback_engine.py         # Deterministic rule-based heuristic summary engine
        ├── prompt_templates.py        # Structured prompt templates with anti-injection guards
        ├── grounding_service.py       # Aggregates DTOs from Feature 004 reporting services
        ├── intent_classifier.py       # Classifies management question intents
        └── insight_service.py         # Main orchestrator (caching, grounding, provider execution, sanitization)

backend/tests/
├── unit/
│   ├── test_ai_fallback_engine.py    # Tests for deterministic rule-based summary
│   ├── test_ai_prompt_sanitization.py # Prompt injection defense tests
│   ├── test_ai_intent_classifier.py  # Intent routing tests
│   └── test_ai_grounding.py          # Grounding data builder tests
└── integration/
    ├── test_ai_insights_api.py       # REST endpoint integration tests with mock provider
    ├── test_ai_caching.py            # SHA-256 cache hit/invalidation tests
    └── test_ai_isolation.py          # Multi-tenant data isolation tests
```

### Frontend
```text
frontend/src/
├── api/
│   └── insights.ts                    # Typed API client for AI insights and Q&A
├── components/
│   └── ai/
│       ├── ExecutiveSummaryCard.tsx   # Prominent narrative insight card on Dashboard
│       ├── ProjectHealthCard.tsx      # Project margin and cash position insight panel
│       ├── FinancialQABox.tsx         # Interactive Q&A chat drawer/panel
│       └── FactVsInterpretationBadge.tsx # Visual badge demarcating verified facts vs AI narrative
```

---

## 5. Implementation Phases & Gateways

1. **Phase 1: Foundation, Grounding & Provider Abstraction**:
   - `AIInsightProvider` interface & `MockAIInsightProvider`
   - Data models (`AIInsightLog`, `AIConversationSession`, `AIConversationMessage`)
   - `GroundingService` pulling authoritative DTOs from Feature 004
   - `DeterministicFallbackEngine` for rule-based summaries
2. **Phase 2: Executive Summary & Project Health Insights (User Stories 1 & 2)**:
   - Structured prompt builders for P&L, Balance Sheet, Cash Flow, and Project Margin
   - Anti-hallucination fact verification sanitizer
   - Backend endpoints `GET /api/v1/insights/executive-summary` and `GET /api/v1/insights/projects/{id}`
   - Frontend `ExecutiveSummaryCard` and `ProjectHealthCard`
3. **Phase 3: Interactive Management Q&A (User Story 3)**:
   - `IntentClassifier` for Indonesian financial queries
   - Conversational session manager and `POST /api/v1/insights/query` endpoint
   - Frontend `FinancialQABox` component
4. **Phase 4: Anomaly Flags & Review Queue Trends (User Story 4)**:
   - Heuristic anomaly signal detector (`UNUSUAL_EXPENSE_SPIKE`, `MARGIN_CRITICAL`, `AR_OVERDUE_SURGE`)
   - `GET /api/v1/insights/anomalies` endpoint
5. **Phase 5: Caching, Hardening, Multi-Tenant Isolation & Quickstart Verification**:
   - SHA-256 payload cache with TTL
   - Multi-tenant isolation test suite
   - Execution of Quickstart Scenarios A through G
