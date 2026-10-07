import io
import uuid
import zipfile
import pytest


def test_retrieve_generated_certificate(client):
    """After a successful job, GET /api/certificates/{recipient_id}/ returns 200 application/pdf."""
    create_res = client.post("/api/jobs/", json={
        "recipients": [{"name": "Sophia Grace", "email": "sophia@example.com"}],
        "template_name": "default"
    })
    assert create_res.status_code == 202
    job_id = create_res.json()["id"]

    rec_res = client.get(f"/api/jobs/{job_id}/recipients/")
    recipient_id = rec_res.json()[0]["id"]

    cert_res = client.get(f"/api/certificates/{recipient_id}/")
    assert cert_res.status_code == 200
    assert cert_res.headers["content-type"] == "application/pdf"
    assert len(cert_res.content) > 0


def test_retrieve_nonexistent_certificate_404(client):
    """GET /api/certificates/{random-uuid}/ returns 404 Not Found."""
    random_id = str(uuid.uuid4())
    res = client.get(f"/api/certificates/{random_id}/")
    assert res.status_code == 404


def test_retrieve_certificate_for_failed_recipient_409(client):
    """A recipient whose certificate generation failed returns 409 Conflict."""
    create_res = client.post("/api/jobs/", json={
        "recipients": [{"name": "", "email": "empty@example.com"}],  # Will fail in generation
    })
    job_id = create_res.json()["id"]

    rec_res = client.get(f"/api/jobs/{job_id}/recipients/")
    recipient = rec_res.json()[0]
    assert recipient["status"] == "FAILED"
    recipient_id = recipient["id"]

    cert_res = client.get(f"/api/certificates/{recipient_id}/")
    assert cert_res.status_code == 409
    assert "generation failed" in cert_res.json()["detail"].lower()


def test_bulk_zip_download(client):
    """GET /api/jobs/{id}/certificates/download returns zip containing all successful certificate PDFs."""
    create_res = client.post("/api/jobs/", json={
        "recipients": [
            {"name": "Winner One", "email": "w1@example.com"},
            {"name": "Winner Two", "email": "w2@example.com"},
            {"name": "", "email": "bad@example.com"},  # Fails, should not be included in zip
        ],
    })
    job_id = create_res.json()["id"]

    download_res = client.get(f"/api/jobs/{job_id}/certificates/download")
    assert download_res.status_code == 200
    assert download_res.headers["content-type"] == "application/zip"
    assert f'filename="job_{job_id}_certificates.zip"' in download_res.headers["content-disposition"]

    zip_buffer = io.BytesIO(download_res.content)
    with zipfile.ZipFile(zip_buffer, "r") as zf:
        file_names = zf.namelist()
        assert len(file_names) == 2
        assert "Winner One.pdf" in file_names
        assert "Winner Two.pdf" in file_names
