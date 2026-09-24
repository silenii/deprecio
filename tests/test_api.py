"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from deprecio.api.main import app

client = TestClient(app)

def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_search_devices_empty_query():
    """Test search with empty query."""
    response = client.get("/api/v1/devices/search")
    assert response.status_code == 422  # Validation error

def test_search_devices():
    """Test device search."""
    response = client.get("/api/v1/devices/search?query=iphone")
    assert response.status_code == 200

def test_get_device():
    """Test get device endpoint."""
    response = client.get("/api/v1/devices/apple-iphone-15")
    assert response.status_code in [200, 404]
