import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from src.core.database import Base


def test_additive_migration_matches_models_and_roundtrips_in_disposable_database():
    path = Path(__file__).parents[2] / "alembic/versions/010_whatsapp_integration.py"
    spec = importlib.util.spec_from_file_location("wa_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine("sqlite:///:memory:")
    names = {name for name in Base.metadata.tables if name.startswith("whatsapp_")}
    with engine.begin() as connection:
        Base.metadata.create_all(connection, tables=[table for table in Base.metadata.sorted_tables if table.name not in names])
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            inspector = sa.inspect(connection)
            for name in names:
                assert {c["name"] for c in inspector.get_columns(name)} == set(Base.metadata.tables[name].columns.keys())
                assert {index["name"] for index in inspector.get_indexes(name)} == {index.name for index in Base.metadata.tables[name].indexes}
            module.downgrade()
            assert not names.intersection(sa.inspect(connection).get_table_names())
            module.upgrade()
            assert names.issubset(sa.inspect(connection).get_table_names())
    engine.dispose()
