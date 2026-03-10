"""
API Tests with Mock (No API Key required)
"""

import pytest
from unittest.mock import patch, MagicMock
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


@patch("app.services.crew_service.Crew")
@patch("app.services.crew_service.Agent")
def test_crew_info_mock(mock_agent, mock_crew):
    """Test Crew info endpoint with mocked CrewAI"""
    # Setup mocks
    mock_agent_instance = MagicMock()
    mock_agent_instance.role = "Researcher"
    mock_agent.return_value = mock_agent_instance
    
    mock_crew_instance = MagicMock()
    mock_crew_instance.agents = [mock_agent_instance]
    mock_crew_instance.tasks = []
    mock_crew.return_value = mock_crew_instance
    
    response = client.get("/api/v1/crew/info")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "agents" in data


@patch("app.services.crew_service.Agent")
def test_list_agents_mock(mock_agent):
    """Test agent list endpoint with mocked Agent"""
    mock_agent_instance = MagicMock()
    mock_agent_instance.role = "Researcher"
    mock_agent_instance.goal = "Research topics"
    mock_agent_instance.backstory = "Expert researcher"
    mock_agent_instance.allow_delegation = False
    mock_agent_instance.verbose = True
    mock_agent.return_value = mock_agent_instance
    
    response = client.get("/api/v1/crew/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
