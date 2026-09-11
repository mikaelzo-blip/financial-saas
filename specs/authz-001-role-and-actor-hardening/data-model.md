# Data Model & Schema Analysis: Role Enforcement & Actor Attribution

**Remediation**: AUTHZ-001 & AUTH-002  
**Specification**: [spec.md](spec.md)  
**Database Migration Required**: **NO**  

---

## 1. Schema Invariance & Migration Decision

A thorough inspection of all SQLAlchemy models and Alembic migrations confirms that **no database schema modifications, table alterations, or migrations are required**.

### Rationale:
- The `User` model already defines `role: UserRole = Column(Enum(UserRole), nullable=False)`.
- The `UserRole` enum already defines all 4 required application roles: `ADMIN`, `MANAGER`, `OPERATOR`, and `VIEWER`.
- The `Transaction` model already includes `created_by: UUID` and `approved_by: UUID`.
- The `AuditLog` model already includes `actor_id: UUID`.
- The `Document` model already includes `created_by: UUID`.
- The `DocumentCorrection` model already includes `corrected_by: UUID`.

The vulnerability exists entirely in the **API dependency injection and authorization validation layer**, where caller-supplied HTTP headers bypass the verified JWT identity.

---

## 2. Existing Relevant Entities

### 2.1 `User` Model (`backend/src/models/user.py`)
```python
class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), nullable=False, default=UserRole.VIEWER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

### 2.2 `AuditLog` Model (`backend/src/models/audit_log.py`)
```python
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    old_values: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
```

### 2.3 `DocumentCorrection` Model (`backend/src/models/document.py`)
```python
class DocumentCorrection(Base):
    __tablename__ = "document_corrections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    corrected_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    changes: Mapped[dict] = mapped_column(JSONB, nullable=False)
    correction_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
```

---

## 3. Actor Attribution Flow (Target Architecture)

```
[JWT Header: Authorization: Bearer <token>]
             │
             ▼
[require_roles / require_application_user]
             │
             ▼  Decodes token claims:
             │  sub: <user_uuid>
             │  organization_id: <org_uuid>
             ▼
[User Principal: current_user]
             │
   ┌─────────┼────────────────────────┐
   │         │                        │
   ▼         ▼                        ▼
[AuditLog]  [DocumentCorrection]   [Transaction]
actor_id =  corrected_by =         created_by =
user.id     user.id                user.id
```

- **Invariance**: No caller-controlled header (`X-User-ID`, `X-Role`) may populate or override these fields.
- **Auditing**: Every mutation emitting audit events must directly consume `current_user.id`.
