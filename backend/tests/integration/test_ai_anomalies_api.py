import pytest
from datetime import date
from src.models.document import Document
from src.models.enums import DocumentType, DocumentProcessingStatus
from tests.integration.test_ai_executive_summary_api import insight_identity

@pytest.mark.asyncio
async def test_anomalies_are_tenant_scoped_and_include_processing_exceptions(client, db_session):
    org, _, headers = await insight_identity(db_session, 'anomaly-a')
    db_session.add(Document(organization_id=org.id, document_code='DOC-A', document_type=DocumentType.RECEIPT, file_name='a.pdf', mime_type='application/pdf', file_size_bytes=1, file_hash='a'*64, storage_path='x', source_channel='WEB_UPLOAD', processing_status=DocumentProcessingStatus.FAILED))
    await db_session.commit()
    response = await client.get('/api/v1/insights/anomalies', headers=headers)
    assert response.status_code == 200
    assert any(item['code'] == 'DOCUMENT_PROCESSING_EXCEPTIONS' for item in response.json()['anomalies'])
