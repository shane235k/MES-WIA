import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root_endpoint():
    """
    Test the fallback root endpoint.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert "MES Backend API is operational" in response.json()["message"]

@pytest.mark.asyncio
async def test_health_endpoint_all_healthy():
    """
    Test the /api/health endpoint when both MongoDB and Redis are connected.
    """
    # Mock the database manager ping_db to return 2.5ms latency
    # and redis manager ping_redis to return 0.75ms latency
    with patch("app.core.database.db_manager.ping_db", new_callable=AsyncMock) as mock_ping_db, \
         patch("app.core.redis.redis_manager.ping_redis", new_callable=AsyncMock) as mock_ping_redis:
        
        mock_ping_db.return_value = 2.5
        mock_ping_redis.return_value = 0.75
        
        response = client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["api"]["status"] == "healthy"
        assert data["database"]["status"] == "healthy"
        assert data["database"]["latency_ms"] == 2.5
        assert data["database"]["error"] is None
        
        assert data["redis"]["status"] == "healthy"
        assert data["redis"]["latency_ms"] == 0.75
        assert data["redis"]["error"] is None

@pytest.mark.asyncio
async def test_health_endpoint_mongodb_degraded():
    """
    Test the /api/health endpoint when MongoDB is unreachable.
    """
    with patch("app.core.database.db_manager.ping_db", new_callable=AsyncMock) as mock_ping_db, \
         patch("app.core.redis.redis_manager.ping_redis", new_callable=AsyncMock) as mock_ping_redis:
        
        # MongoDB throws a connection error, Redis is fine
        mock_ping_db.side_effect = ConnectionError("MongoDB selection timeout")
        mock_ping_redis.return_value = 0.42
        
        response = client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Overall status is degraded
        assert data["status"] == "degraded"
        assert data["api"]["status"] == "healthy"
        
        # MongoDB is unreachable
        assert data["database"]["status"] == "unreachable"
        assert data["database"]["latency_ms"] is None
        assert "MongoDB selection timeout" in data["database"]["error"]
        
        # Redis is healthy
        assert data["redis"]["status"] == "healthy"
        assert data["redis"]["latency_ms"] == 0.42

@pytest.mark.asyncio
async def test_health_endpoint_redis_degraded():
    """
    Test the /api/health endpoint when Redis is unreachable.
    """
    with patch("app.core.database.db_manager.ping_db", new_callable=AsyncMock) as mock_ping_db, \
         patch("app.core.redis.redis_manager.ping_redis", new_callable=AsyncMock) as mock_ping_redis:
        
        # MongoDB is healthy, Redis throws connection error
        mock_ping_db.return_value = 1.15
        mock_ping_redis.side_effect = ConnectionError("Redis socket timeout")
        
        response = client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Overall status is degraded
        assert data["status"] == "degraded"
        assert data["api"]["status"] == "healthy"
        
        # MongoDB is healthy
        assert data["database"]["status"] == "healthy"
        assert data["database"]["latency_ms"] == 1.15
        
        # Redis is unreachable
        assert data["redis"]["status"] == "unreachable"
        assert data["redis"]["latency_ms"] is None
        assert "Redis socket timeout" in data["redis"]["error"]

@pytest.mark.asyncio
async def test_health_endpoint_both_degraded():
    """
    Test the /api/health endpoint when both services are unreachable.
    """
    with patch("app.core.database.db_manager.ping_db", new_callable=AsyncMock) as mock_ping_db, \
         patch("app.core.redis.redis_manager.ping_redis", new_callable=AsyncMock) as mock_ping_redis:
        
        mock_ping_db.side_effect = ConnectionError("MongoDB selection timeout")
        mock_ping_redis.side_effect = ConnectionError("Redis socket timeout")
        
        response = client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "degraded"
        assert data["api"]["status"] == "healthy"
        assert data["database"]["status"] == "unreachable"
        assert data["redis"]["status"] == "unreachable"
