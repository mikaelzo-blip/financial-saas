"""Tenant-scoped advisory cache/audit records; no financial mutation links."""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from src.core.database import Base


class AIInsightLog(Base):
    __tablename__ = 'ai_insight_logs'
    __table_args__ = (Index('idx_ai_cache_lookup', 'organization_id', 'prompt_payload_hash', 'expires_at'), Index('idx_ai_insight_org_type', 'organization_id', 'insight_type', 'created_at'))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organizations.id'), nullable=False)
    insight_type: Mapped[str] = mapped_column(String(32), nullable=False)
    period_key: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), 'postgresql'), nullable=False)
    provider_used: Mapped[str] = mapped_column(String(32), nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, server_default='0', nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, server_default='0', nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AIConversationSession(Base):
    __tablename__ = 'ai_conversation_sessions'
    __table_args__ = (Index('idx_ai_session_user', 'user_id', 'updated_at'), Index('idx_ai_session_org', 'organization_id'))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organizations.id'), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    session_title: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AIConversationMessage(Base):
    __tablename__ = 'ai_conversation_messages'
    __table_args__ = (Index('idx_ai_message_session', 'session_id', 'created_at'),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('ai_conversation_sessions.id'), nullable=False)
    sender: Mapped[str] = mapped_column(String(16), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_intent: Mapped[str | None] = mapped_column(String(32))
    source_references: Mapped[list | None] = mapped_column(JSON().with_variant(JSONB(), 'postgresql'))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, server_default='0', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
