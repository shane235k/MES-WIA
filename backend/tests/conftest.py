import sys
import pytest
from pathlib import Path
from app.core.database import db_manager

# Add the parent directory (backend root) to sys.path so pytest can find the app module
backend_root = str(Path(__file__).parent.parent.resolve())
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

@pytest.fixture(autouse=True)
async def init_test_db():
    """
    Ensure the test database is active and maps to 'mes_test_db' for every test run.
    Re-creates the client to bind to the current event loop.
    Cleans up database collections to keep tests isolated.
    """
    # Force disconnect and reconnect to bind to the active loop of this test
    await db_manager.disconnect()
    await db_manager.connect()
    
    # Target isolated test database
    db_manager.db = db_manager.client["mes_test_db"]
    await db_manager.create_indexes()
    
    yield db_manager.db
    
    # Clear collections to ensure test isolation
    db = db_manager.db
    collections = await db.list_collection_names()
    for col in collections:
        if not col.startswith("system."):
            await db[col].delete_many({})
