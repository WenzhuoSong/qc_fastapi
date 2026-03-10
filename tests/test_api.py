"""
API Tests
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    """Test root path"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert "status" in data


def test_health_check():
    """Test health check"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_api_health():
    """Test API health check"""
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_crew_info():
    """Test Crew info endpoint"""
    response = client.get("/api/v1/crew/info")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "agents" in data
    assert "tasks" in data


def test_list_agents():
    """Test agent list endpoint"""
    response = client.get("/api/v1/crew/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert len(data["agents"]) > 0
