import uuid
import pytest
from app.models import CertificateJob, CertificateRecipient


def test_create_job_valid(client):
    """POST /api/jobs/ with valid recipients returns 202 and correct job summary."""
    payload = {
        "recipients": [
            {"name": "Alice Johnson", "email": "alice@example.com", "extra_fields": {"Course": "Python"}},
            {"name": "Bob Smith", "email": "bob@example.com", "extra_fields": {"Course": "FastAPI"}},
            {"name": "Charlie Brown", "email": "charlie@example.com", "extra_fields": {}},
        ],
        "template_name": "default",
    }
    response = client.post("/api/jobs/", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "id" in data
    assert data["total_count"] == 3


def test_create_job_empty_recipients_rejected(client):
    """POST /api/jobs/ with empty recipients list returns 422 Unprocessable Entity."""
    response = client.post("/api/jobs/", json={"recipients": []})
    assert response.status_code == 422


def test_create_job_missing_required_field_rejected(client):
    """POST /api/jobs/ with missing recipient name returns 422."""
    payload = {
        "recipients": [
            {"email": "alice@example.com"}  # missing "name"
        ]
    }
    response = client.post("/api/jobs/", json=payload)
    assert response.status_code == 422


def test_job_status_aggregation(client):
    """Assert status computation aggregates counts and overall_status correctly when one fails."""
    payload = {
        "recipients": [
            {"name": "Valid Recipient", "email": "valid@example.com", "extra_fields": {}},
            {"name": "   ", "email": "bad@example.com", "extra_fields": {}},  # whitespace triggers InvalidRecipientError
        ],
        "template_name": "default",
    }
    create_res = client.post("/api/jobs/", json=payload)
    assert create_res.status_code == 202
    job_id = create_res.json()["id"]

    # Since tasks execute eagerly, task execution has already completed
    status_res = client.get(f"/api/jobs/{job_id}/")
    assert status_res.status_code == 200
    data = status_res.json()
    assert data["id"] == job_id
    assert data["total_count"] == 2
    assert data["success_count"] == 1
    assert data["failure_count"] == 1
    assert data["pending_count"] == 0
    assert data["overall_status"] == "COMPLETED_WITH_ERRORS"


def test_one_bad_recipient_does_not_block_others(client):
    """Explicitly verify failure-isolation: 3 valid + 1 invalid recipient -> 3 SUCCESS, 1 FAILED."""
    payload = {
        "recipients": [
            {"name": "Valid 1", "email": "v1@example.com", "extra_fields": {}},
            {"name": "", "email": "invalid@example.com", "extra_fields": {}},  # Empty name forces validation failure
            {"name": "Valid 2", "email": "v2@example.com", "extra_fields": {}},
            {"name": "Valid 3", "email": "v3@example.com", "extra_fields": {}},
        ],
        "template_name": "default",
    }
    create_res = client.post("/api/jobs/", json=payload)
    assert create_res.status_code == 202
    job_id = create_res.json()["id"]

    recipients_res = client.get(f"/api/jobs/{job_id}/recipients/")
    assert recipients_res.status_code == 200
    recipients = recipients_res.json()
    assert len(recipients) == 4

    successful = [r for r in recipients if r["status"] == "SUCCESS"]
    failed = [r for r in recipients if r["status"] == "FAILED"]

    assert len(successful) == 3
    assert len(failed) == 1

    failed_recipient = failed[0]
    assert failed_recipient["error_message"] is not None
    assert len(failed_recipient["error_message"]) > 0
    assert "Recipient name cannot be empty" in failed_recipient["error_message"]

    # Check overall job status reflects partial success
    status_res = client.get(f"/api/jobs/{job_id}/")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["success_count"] == 3
    assert status_data["failure_count"] == 1
    assert status_data["pending_count"] == 0
    assert status_data["overall_status"] == "COMPLETED_WITH_ERRORS"


def test_job_not_found_returns_404(client):
    """GET /api/jobs/{random_uuid}/ returns 404 Not Found."""
    random_id = str(uuid.uuid4())
    response = client.get(f"/api/jobs/{random_id}/")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_recipients_list_endpoint(client):
    """GET /api/jobs/{id}/recipients/ returns all recipients ordered alphabetically by name."""
    payload = {
        "recipients": [
            {"name": "Zachary", "email": "z@example.com", "extra_fields": {}},
            {"name": "Abigail", "email": "a@example.com", "extra_fields": {}},
            {"name": "Liam", "email": "l@example.com", "extra_fields": {}},
        ],
    }
    create_res = client.post("/api/jobs/", json=payload)
    job_id = create_res.json()["id"]

    res = client.get(f"/api/jobs/{job_id}/recipients/")
    assert res.status_code == 200
    recipients = res.json()
    assert len(recipients) == 3

    names = [r["name"] for r in recipients]
    assert names == ["Abigail", "Liam", "Zachary"]
    for r in recipients:
        assert r["status"] == "SUCCESS"
        assert r["generated_at"] is not None


def test_idempotent_job_submission(client, db_session):
    """Submitting with the same Idempotency-Key within 24h returns the existing job without duplicates."""
    payload = {
        "recipients": [
            {"name": "Idempotent Donor", "email": "donor@example.com"}
        ],
    }
    headers = {"Idempotency-Key": "unique-batch-key-999"}

    # First submission
    res1 = client.post("/api/jobs/", json=payload, headers=headers)
    assert res1.status_code == 202
    job_id_1 = res1.json()["id"]

    # Duplicate submission with same key
    res2 = client.post("/api/jobs/", json=payload, headers=headers)
    assert res2.status_code == 202
    job_id_2 = res2.json()["id"]

    # Must return the exact same job ID
    assert job_id_1 == job_id_2

    # Assert only 1 CertificateJob was created in the database
    job_count = db_session.query(CertificateJob).filter(CertificateJob.idempotency_key == "unique-batch-key-999").count()
    assert job_count == 1
