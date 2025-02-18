from fastapi.testclient import TestClient
import pytest
from main import app, tracked_cities, Location

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_tracked_cities():
    """This fixture runs before every test and clears the tracked cities."""
    tracked_cities.clear()

def test_add_city():
    city = "Санкт-Петербург"
    latitude = 59.95
    longitude = 30.316
    response = client.post("/tracking", json={
        "city": city,
        "location": {"latitude": latitude, "longitude": longitude}
    })
    assert response.status_code == 200
    assert tracked_cities[city] == (Location(latitude=latitude, longitude=longitude), [])

def test_show_tracked():
    """Add 'Санкт-Петербург' into forecast-tracking map by PUT request at /tracking and ensure it is returned on GET request at /tracking."""
    city = "Санкт-Петербург"
    latitude = 59.95
    longitude = 30.316
    response = client.post("/tracking", json={
        "city": city,
        "location": {"latitude": latitude, "longitude": longitude}
    })
    assert response.status_code == 200
    assert tracked_cities[city] == (Location(latitude=latitude, longitude=longitude), [])

    response = client.get("/tracking")
    assert response.status_code == 200
    assert response.json() == { "cities": [city] }

def test_no_tracked_cities():
    """Since `tracked_cities` is cleared before this test, it should return an empty list of cities."""
    response = client.get("/tracking")
    assert response.status_code == 200
    assert response.json() == { "cities": [] }