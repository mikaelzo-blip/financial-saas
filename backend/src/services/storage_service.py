import os
import shutil
import uuid
from typing import BinaryIO, Optional
from datetime import datetime
from pathlib import Path

from src.core.config import settings


class StorageService:
    """
    Handles immutable raw document persistence on filesystem / object storage.
    Path layout: storage/documents/{org_id}/{YYYY}/{MM}/{file_id}.{ext}
    """
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or settings.STORAGE_DIR)

    def save_file(
        self,
        organization_id: uuid.UUID,
        file_obj: BinaryIO,
        original_filename: str
    ) -> str:
        now = datetime.now()
        ext = Path(original_filename).suffix
        file_id = uuid.uuid4().hex

        rel_dir = Path(str(organization_id)) / f"{now.year}" / f"{now.month:02d}"
        target_dir = self.base_dir / "documents" / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / f"{file_id}{ext}"

        file_obj.seek(0)
        with open(target_file, "wb") as f:
            shutil.copyfileobj(file_obj, f)

        # Return relative storage path for DB
        return str(Path("documents") / rel_dir / f"{file_id}{ext}").replace("\\", "/")

    def get_file_path(self, storage_path: str) -> Path:
        return self.base_dir / storage_path
