from pathlib import Path

from src.core.config import settings
from src.services.storage_service import StorageService


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_relative_storage_configuration_is_repository_relative(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", "backend/storage")

    service = StorageService()

    assert service.base_dir == (REPOSITORY_ROOT / "backend" / "storage").resolve()


def test_windows_startup_uses_checkout_storage_for_backend_and_worker():
    startup = (REPOSITORY_ROOT / "scripts" / "windows" / "Start-Financial-SaaS.ps1").read_text(
        encoding="utf-8"
    )

    assert r"C:\financial-saas\storage" not in startup
    assert "$Storage = Join-Path $Backend 'storage'" in startup
    assert "$backendProcessEnv = @{ STORAGE_DIR = $Storage }" in startup
    assert (
        "Start-TrackedBackgroundProcess 'backend' $Python "
        "@('-m','uvicorn','src.main:app','--host','127.0.0.1','--port','8000') "
        "$Backend 'backend' $backendProcessEnv"
    ) in startup
    assert (
        "Start-TrackedBackgroundProcess 'worker' $Python @('-m','src.worker') "
        "$Backend 'worker' $backendProcessEnv"
    ) in startup
