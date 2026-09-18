import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from src.core.database import Base


def test_additive_migration_matches_models_and_roundtrips_in_disposable_database():
    path_010 = Path(__file__).parents[2] / "alembic/versions/010_whatsapp_integration.py"
    spec_010 = importlib.util.spec_from_file_location("wa_migration_010", path_010)
    module_010 = importlib.util.module_from_spec(spec_010)
    spec_010.loader.exec_module(module_010)

    path_029 = Path(__file__).parents[2] / "alembic/versions/029_whatsapp_document_sessions.py"
    spec_029 = importlib.util.spec_from_file_location("wa_migration_029", path_029)
    module_029 = importlib.util.module_from_spec(spec_029)
    spec_029.loader.exec_module(module_029)

    engine = sa.create_engine("sqlite:///:memory:")
    names = {name for name in Base.metadata.tables if name.startswith("whatsapp_")}
    with engine.begin() as connection:
        Base.metadata.create_all(connection, tables=[table for table in Base.metadata.sorted_tables if table.name not in names])
        with Operations.context(MigrationContext.configure(connection)):
            module_010.upgrade()
            module_029.upgrade()
            inspector = sa.inspect(connection)
            for name in names:
                assert {c["name"] for c in inspector.get_columns(name)} == set(Base.metadata.tables[name].columns.keys())
                assert {index["name"] for index in inspector.get_indexes(name)} == {index.name for index in Base.metadata.tables[name].indexes}
            module_029.downgrade()
            module_010.downgrade()
            assert not names.intersection(sa.inspect(connection).get_table_names())
            module_010.upgrade()
            module_029.upgrade()
            assert names.issubset(sa.inspect(connection).get_table_names())
    engine.dispose()
