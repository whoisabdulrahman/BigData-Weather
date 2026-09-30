from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)


def test_submit_valid_citizen_report():
    payload = {
        "text": "Severe waterlogging near MG Road metro station, vehicles submerged.",
        "event_type": "FLOOD",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "state": "Karnataka",
        "city": "Bengaluru",
        "location_provenance": "gps",
        "media_urls": ["https://storage.bwip.gov.in/media/sample1.jpg"]
    }
    response = client.post("/api/v1/citizen/reports", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "id" in data
    assert "reference_number" in data
    assert data["reference_number"].startswith("BWIP-")
    assert data["status"] == "ACCEPTED"
    assert data["processing_status"] == "ACCEPTED"



def test_reject_citizen_report_outside_india_bounding_box():
    # Latitude 50.0 is outside India's bounds (6°N - 38°N)
    payload = {
        "text": "Submerged vehicles in invalid region.",
        "event_type": "FLOOD",
        "latitude": 50.0,
        "longitude": 77.0,
        "state": "Unknown",
    }
    response = client.post("/api/v1/citizen/reports", json=payload)
    assert response.status_code == 422


def test_reject_citizen_report_too_short_text():
    payload = {
        "text": "Rain",
        "event_type": "RAIN",
        "latitude": 18.0,
        "longitude": 75.0,
        "state": "Maharashtra",
    }
    response = client.post("/api/v1/citizen/reports", json=payload)
    assert response.status_code == 422


def test_list_incidents_and_filter():
    response = client.get("/api/v1/incidents?severity=HIGH")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) >= 1
    for item in data["items"]:
        assert item["severity"] == "HIGH"
