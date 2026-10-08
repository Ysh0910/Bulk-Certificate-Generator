import uuid
import pytest
from unittest.mock import MagicMock
from app.config import settings
from app.models import CertificateJob, CertificateRecipient
import app.tasks as tasks_module


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


def test_create_job_invalid_email_rejected(client):
    """POST /api/jobs/ with invalid email address format returns 422 Unprocessable Entity."""
    payload = {
        "recipients": [
            {"name": "Alice Johnson", "email": "not-a-valid-email"}
        ]
    }
    response = client.post("/api/jobs/", json=payload)
    assert response.status_code == 422


def test_create_job_batch_cap_exceeded_rejected(client, monkeypatch):
    """POST /api/jobs/ exceeding MAX_RECIPIENTS_PER_JOB returns 422 with split instructions."""
    monkeypatch.setattr(settings, "MAX_RECIPIENTS_PER_JOB", 2)
    payload = {
        "recipients": [
            {"name": "User One", "email": "u1@example.com"},
            {"name": "User Two", "email": "u2@example.com"},
            {"name": "User Three", "email": "u3@example.com"},
        ]
    }
    response = client.post("/api/jobs/", json=payload)
    assert response.status_code == 422
    error_text = response.text
    assert "exceeds maximum limit of 2" in error_text
    assert "split the batch" in error_text


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

    status_res = client.get(f"/api/jobs/{job_id}/")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["success_count"] == 3
    assert status_data["failure_count"] == 1
    assert status_data["pending_count"] == 0
    assert status_data["overall_status"] == "COMPLETED_WITH_ERRORS"


def test_failure_injection_via_mocked_generator(client, monkeypatch):
    """Inject failure into generator for a specific recipient: row FAILED with error, others SUCCESS."""
    original_generate = tasks_module.generate_certificate

    def mock_generate(recipient_name, extra_fields, output_path, template_path):
        if recipient_name == "Faulty Donor":
            raise RuntimeError("Injected generator rendering failure")
        return original_generate(recipient_name, extra_fields, output_path, template_path)

    monkeypatch.setattr(tasks_module, "generate_certificate", mock_generate)

    payload = {
        "recipients": [
            {"name": "Healthy Donor 1", "email": "h1@example.com"},
            {"name": "Faulty Donor", "email": "faulty@example.com"},
            {"name": "Healthy Donor 2", "email": "h2@example.com"},
        ]
    }
    create_res = client.post("/api/jobs/", json=payload)
    assert create_res.status_code == 202
    job_id = create_res.json()["id"]

    status_res = client.get(f"/api/jobs/{job_id}/")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["success_count"] == 2
    assert status_data["failure_count"] == 1
    assert status_data["overall_status"] == "COMPLETED_WITH_ERRORS"

    rec_res = client.get(f"/api/jobs/{job_id}/recipients/")
    recipients = rec_res.json()
    faulty_rec = next(r for r in recipients if r["name"] == "Faulty Donor")
    assert faulty_rec["status"] == "FAILED"
    assert "Injected generator rendering failure" in faulty_rec["error_message"]


def test_duplicate_task_execution_does_not_regenerate(client, monkeypatch):
    """Executing generate_certificate_task twice for one recipient calls generator exactly once."""
    call_count = 0
    original_generate = tasks_module.generate_certificate

    def counting_generate(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original_generate(*args, **kwargs)

    monkeypatch.setattr(tasks_module, "generate_certificate", counting_generate)

    create_res = client.post("/api/jobs/", json={
        "recipients": [{"name": "Single Donor", "email": "single@example.com"}]
    })
    assert create_res.status_code == 202
    job_id = create_res.json()["id"]

    rec_res = client.get(f"/api/jobs/{job_id}/recipients/")
    rec_id = rec_res.json()[0]["id"]
    assert call_count == 1

    # Directly run the task a second time for the same recipient
    tasks_module.generate_certificate_task(str(rec_id))

    # Generator should NOT have been invoked again because recipient is already SUCCESS
    assert call_count == 1


def test_idempotent_job_submission(client, db_session):
    """Submitting with the same Idempotency-Key within 24h returns existing job without duplicates."""
    payload = {
        "recipients": [
            {"name": "Idempotent Donor", "email": "donor@example.com"}
        ],
    }
    headers = {"Idempotency-Key": "unique-batch-key-999"}

    res1 = client.post("/api/jobs/", json=payload, headers=headers)
    assert res1.status_code == 202
    job_id_1 = res1.json()["id"]

    res2 = client.post("/api/jobs/", json=payload, headers=headers)
    assert res2.status_code == 202
    job_id_2 = res2.json()["id"]

    assert job_id_1 == job_id_2
    job_count = db_session.query(CertificateJob).filter(CertificateJob.idempotency_key == "unique-batch-key-999").count()
    assert job_count == 1


def test_idempotent_different_key_creates_new_job(client):
    """Different Idempotency-Keys create separate jobs."""
    payload = {"recipients": [{"name": "Donor", "email": "d@example.com"}]}
    res1 = client.post("/api/jobs/", json=payload, headers={"Idempotency-Key": "key-1"})
    res2 = client.post("/api/jobs/", json=payload, headers={"Idempotency-Key": "key-2"})

    assert res1.status_code == 202
    assert res2.status_code == 202
    assert res1.json()["id"] != res2.json()["id"]


def test_idempotent_key_reused_with_different_payload_returns_422(client):
    """Reusing the same Idempotency-Key with a different payload returns 422 Unprocessable Entity."""
    headers = {"Idempotency-Key": "payload-check-key-123"}
    payload1 = {"recipients": [{"name": "Donor One", "email": "d1@example.com"}]}
    payload2 = {"recipients": [{"name": "Donor Two", "email": "d2@example.com"}]}

    res1 = client.post("/api/jobs/", json=payload1, headers=headers)
    assert res1.status_code == 202

    res2 = client.post("/api/jobs/", json=payload2, headers=headers)
    assert res2.status_code == 422
    assert "reused with a different request body" in res2.json()["detail"]


def test_broker_unavailable_at_submit_returns_503(client, db_session, monkeypatch):
    """When the task broker is unavailable during submit, API returns 503 with job_id and rows remain PENDING."""
    def mock_delay_fail(*args, **kwargs):
        raise ConnectionError("Redis broker connection timeout")

    monkeypatch.setattr(tasks_module.generate_certificate_task, "delay", mock_delay_fail)

    payload = {"recipients": [{"name": "Pending Donor", "email": "pending@example.com"}]}
    res = client.post("/api/jobs/", json=payload)
    assert res.status_code == 503
    data = res.json()
    assert "job_id" in data
    assert "temporarily unavailable" in data["detail"]

    # Verify rows were committed and remain in PENDING state
    job_id = uuid.UUID(data["job_id"])
    recipients = db_session.query(CertificateRecipient).filter(CertificateRecipient.job_id == job_id).all()
    assert len(recipients) == 1
    assert recipients[0].status == "PENDING"


def test_retry_endpoint_requeues_only_non_success(client, monkeypatch):
    """POST /api/jobs/{job_id}/retry recovers only failed recipients, leaving successful ones untouched."""
    should_fail = True
    call_counts = {"Recipient A": 0, "Recipient B": 0}
    original_generate = tasks_module.generate_certificate

    def mock_generate(recipient_name, extra_fields, output_path, template_path):
        call_counts[recipient_name] = call_counts.get(recipient_name, 0) + 1
        if recipient_name == "Recipient B" and should_fail:
            raise RuntimeError("Transient rendering error")
        return original_generate(recipient_name, extra_fields, output_path, template_path)

    monkeypatch.setattr(tasks_module, "generate_certificate", mock_generate)

    payload = {
        "recipients": [
            {"name": "Recipient A", "email": "a@example.com"},
            {"name": "Recipient B", "email": "b@example.com"},
        ]
    }
    create_res = client.post("/api/jobs/", json=payload)
    assert create_res.status_code == 202
    job_id = create_res.json()["id"]

    # Verify initial state: A succeeded (1 call), B failed (1 call)
    status_before = client.get(f"/api/jobs/{job_id}/").json()
    assert status_before["success_count"] == 1
    assert status_before["failure_count"] == 1
    assert call_counts["Recipient A"] == 1
    assert call_counts["Recipient B"] == 1

    # Now recover the transient failure and trigger retry
    should_fail = False
    retry_res = client.post(f"/api/jobs/{job_id}/retry")
    assert retry_res.status_code == 202
    assert retry_res.json()["requeued_count"] == 1

    # Check that only B was regenerated (call count for B is 2, A remains 1)
    assert call_counts["Recipient A"] == 1
    assert call_counts["Recipient B"] == 2

    # Job is now fully completed
    status_after = client.get(f"/api/jobs/{job_id}/").json()
    assert status_after["success_count"] == 2
    assert status_after["failure_count"] == 0
    assert status_after["overall_status"] == "COMPLETED"

    # Calling retry again when all are SUCCESS returns 200 with requeued_count == 0
    retry_again = client.post(f"/api/jobs/{job_id}/retry")
    assert retry_again.status_code == 200
    assert retry_again.json()["requeued_count"] == 0


def test_retry_endpoint_unknown_job_404(client):
    """POST /api/jobs/{random_uuid}/retry returns 404 Not Found."""
    random_id = str(uuid.uuid4())
    res = client.post(f"/api/jobs/{random_id}/retry")
    assert res.status_code == 404


def test_job_not_found_returns_404(client):
    """GET /api/jobs/{random_uuid}/ returns 404 Not Found."""
    random_id = str(uuid.uuid4())
    response = client.get(f"/api/jobs/{random_id}/")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_malformed_job_uuid_returns_422(client):
    """GET /api/jobs/{not-a-uuid}/ returns 422 Unprocessable Entity."""
    response = client.get("/api/jobs/not-a-valid-uuid/")
    assert response.status_code == 422


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
