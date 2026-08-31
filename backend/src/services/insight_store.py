"""Application persistence boundary. AI providers cannot import/use this store."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from src.models.ai_insight import AIInsightLog
from src.models.audit import AuditLog
from uuid import uuid5, NAMESPACE_URL
from src.schemas.ai_insight import AIInsightResponse


class InsightStore:
    def __init__(self, db, organization_id):
        self.db = db
        self.organization_id = organization_id

    async def get(self, payload):
        if payload.organization_id != self.organization_id:
            raise PermissionError('Organization mismatch')
        log = await self.db.scalar(select(AIInsightLog).where(
            AIInsightLog.organization_id == self.organization_id,
            AIInsightLog.prompt_payload_hash == payload.cache_key(),
            AIInsightLog.expires_at > datetime.now(timezone.utc),
        ).order_by(AIInsightLog.created_at.desc()).limit(1))
        if log:
            response = AIInsightResponse.model_validate(log.response_json)
            if response.organization_id != self.organization_id:
                raise PermissionError('Invalid cached organization')
            response.provider_metadata.cached = True
            return response
        return None

    async def put(self, payload, response, ttl=3600):
        if payload.organization_id != self.organization_id or response.organization_id != self.organization_id:
            raise PermissionError('Organization mismatch')
        self.db.add(AIInsightLog(organization_id=self.organization_id, insight_type=payload.insight_type,
            period_key=f'{payload.start_date}:{payload.end_date}', prompt_payload_hash=payload.cache_key(),
            response_json=response.model_dump(mode='json'), provider_used=response.provider_metadata.provider,
            tokens_used=response.provider_metadata.tokens_used, latency_ms=response.provider_metadata.latency_ms,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl)))
        await self.db.flush()
        self.db.add(AuditLog(organization_id=self.organization_id, entity_name='AIInsight', entity_id=uuid5(NAMESPACE_URL, payload.cache_key()), action='INSIGHT_GENERATED', old_values=None, new_values={'insight_type': payload.insight_type, 'provider': response.provider_metadata.provider}, actor_id=None, reason='Advisory insight audit'))
