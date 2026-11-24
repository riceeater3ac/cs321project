
from app import app


def test_dashboard_after_login():
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user"] = "student@gmu.edu"

        response = client.get("/main")
        assert response.status_code == 200


def test_report_lost_page():
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user"] = "student@gmu.edu"

        response = client.get("/report-lost")
        assert response.status_code == 200


def test_report_found_page():
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user"] = "student@gmu.edu"

        response = client.get("/report-found")
        assert response.status_code == 200


def test_report_found_without_login():
    with app.test_client() as client:
        response = client.get("/report-found")
        assert response.status_code == 302


def test_verification_without_email():
    with app.test_client() as client:
        response = client.get("/validate")
        assert response.status_code == 302


def test_logout_clears_session():
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user"] = "student@gmu.edu"

        client.get("/logout")

        with client.session_transaction() as session:
            assert "user" not in session
