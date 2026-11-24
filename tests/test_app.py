
from app import app


def test_home_page():
    with app.test_client() as client:
        response = client.get("/")
        assert response.status_code == 200


def test_invalid_page():
    with app.test_client() as client:
        response = client.get("/invalid-page")
        assert response.status_code == 404


def test_logout():
    with app.test_client() as client:
        response = client.get("/logout")
        assert response.status_code == 302


def test_unauthorized_access():
    with app.test_client() as client:
        response = client.get("/main")
        assert response.status_code == 302
