from fastapi.testclient import TestClient
from app import app


client = TestClient(app)


def test_ad_entitlement_defaults_to_show_ads_for_anonymous():
    r = client.get("/ads/entitlement/not_signed_in")
    assert r.status_code == 200
    data = r.json()
    assert data["show_ads"] is True
    assert data["ad_free"] is False

