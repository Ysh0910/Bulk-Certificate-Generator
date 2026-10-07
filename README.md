# Bulk Certificate Generator

A high-throughput, resilient certificate generation backend built with FastAPI, Celery, Redis, PostgreSQL, and Pillow.

---

## Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd cert-generator
   ```

2. **Configure environment variables**:
   Create a `.env` file from [.env.example](file:///c:/Users/yash5/Desktop/Projects/Aereo/cert-generator/.env.example):
   ```bash
   cp .env.example .env
   ```
   Default settings:
   - `DATABASE_URL=postgresql://postgres:postgres@db:5432/certgen`
   - `REDIS_URL=redis://redis:6379/0`
   - `GENERATED_DIR=app/generated`
   - `TEMPLATES_DIR=app/templates`

3. **Build and start the services**:
   ```bash
   docker compose up --build
   ```

---

## Running the Application

Once started via Docker Compose, all four services (`db`, `redis`, `api`, and `worker`) will initialize automatically:
- **API Server**: Available at [http://localhost:8000](http://localhost:8000)
- **Health Check**: `GET http://localhost:8000/health`
- **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative Documentation (ReDoc)**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Running Tests

Tests run against an isolated in-memory SQLite database and use Celery's eager execution mode (`task_always_eager = True`). This means **neither Redis nor an active Celery worker is required to run the test suite**—the full workflow (job creation, asynchronous task execution, and status aggregation) executes synchronously in-process.

To run the tests locally:
```bash
# In your virtual environment with test dependencies installed:
pytest -v
```

*(Note: While tests run without Redis or background workers, running workers via Docker Compose is required for actual asynchronous production workloads).*

---

## Submitting a Certificate Generation Request

Submit a batch of recipients to `POST /api/jobs/` (optionally including an `Idempotency-Key` header to prevent duplicate job processing):

```bash
curl -X POST http://localhost:8000/api/jobs/ \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: batch-2026-10-07-001" \
  -d '{
    "recipients": [
      {
        "name": "Dr. Elena Vance",
        "email": "elena@example.com",
        "extra_fields": {
          "blood_group": "O+",
          "donation_date": "2026-10-07",
          "camp_name": "City Blood Center",
          "organization": "Red Cross",
          "units_donated": "1 unit"
        }
      },
      {
        "name": "Gordon Freeman",
        "email": "gordon@example.com",
        "extra_fields": {
          "blood_group": "A+",
          "donation_date": "2026-10-07",
          "camp_name": "City Blood Center",
          "organization": "Red Cross",
          "units_donated": "2 units"
        }
      }
    ],
    "template_name": "default"
  }'
```

**Expected 202 Response**:
```json
{
  "id": "e6a4b3d8-5c91-4cfa-81a2-7fa3456789ab",
  "total_count": 2
}
```

---

## Checking Job Status

Query the live job processing status at `GET /api/jobs/{id}/`:

```bash
curl -X GET http://localhost:8000/api/jobs/e6a4b3d8-5c91-4cfa-81a2-7fa3456789ab/
```

**Response**:
```json
{
  "id": "e6a4b3d8-5c91-4cfa-81a2-7fa3456789ab",
  "created_at": "2026-10-07T10:15:30.123456",
  "total_count": 2,
  "success_count": 2,
  "failure_count": 0,
  "pending_count": 0,
  "overall_status": "COMPLETED"
}
```

*(Possible `overall_status` values: `PROCESSING`, `COMPLETED`, or `COMPLETED_WITH_ERRORS`).*

You can also list all individual recipient statuses ordered by name:
```bash
curl -X GET http://localhost:8000/api/jobs/e6a4b3d8-5c91-4cfa-81a2-7fa3456789ab/recipients/
```

---

## Retrieving Certificates

### 1. Single Certificate Download
Download a specific recipient's certificate PDF (returns `409 Conflict` if still processing or failed):

```bash
curl -X GET http://localhost:8000/api/certificates/3fa85f64-5717-4562-b3fc-2c963f66afa6/ \
  --output "Elena_Vance_certificate.pdf"
```

### 2. Bulk Zip Download
Download all successful certificates for a job bundled inside a zip archive:

```bash
curl -X GET http://localhost:8000/api/jobs/e6a4b3d8-5c91-4cfa-81a2-7fa3456789ab/certificates/download \
  --output "job_certificates.zip"
```

---

## Important Design Decisions

- **Celery + Redis over FastAPI BackgroundTasks**: FastAPI's in-process `BackgroundTasks` run on the same asyncio thread pool as the API server. If the server process crashes, restarts, or deploys, any in-flight background jobs are permanently lost. Celery backed by Redis guarantees persistent queues, durable message delivery, automatic worker concurrency, and horizontal scalability across multiple machines.
- **One Celery Task Per Recipient (Failure Isolation)**: Instead of dispatching a single monolithic batch task for all recipients in a job, individual tasks are dispatched per recipient (`generate_certificate_task.delay(recipient.id)`). This guarantees strict failure isolation: an unhandled exception or invalid data for one recipient (such as a missing name) fails only that specific recipient row without crashing or delaying the rest of the batch.
- **Live-Computed Job Status (No Counter Columns on Job)**: Job status (`overall_status`, `success_count`, `failure_count`, `pending_count`) is calculated on the fly from `CertificateRecipient` rows via database aggregation (`group_by`) when read. Eliminating counters and status fields on the parent `CertificateJob` table eliminates database lock contention and race conditions when dozens of Celery workers process recipients simultaneously.
- **24-Hour API Idempotency & Task Retries**: The `POST /api/jobs/` endpoint accepts an `Idempotency-Key` header. If the exact same key is submitted within 24 hours, the server immediately returns the existing job ID without duplicating rows or re-dispatching tasks. Additionally, Celery tasks implement task-level idempotency (skipping already-generated `SUCCESS` certificates) and exponential backoff retries for transient exceptions (`max_retries=3`), while failing permanently without retry on validation errors.
- **Pillow for Certificate Generation**: Pillow was chosen because it is pure Python/C-wheel based with zero reliance on heavy external system libraries (unlike WeasyPrint or headless browser solutions which require Cairo, Pango, or Chromium). This keeps Docker build times extremely fast, avoids binary bloat, and allows procedural on-the-fly certificate generation even when no template image file is provided.
- **One-Command Docker Compose**: The entire multi-service stack (`api`, `worker`, `db`, and `redis`) is unified in [docker-compose.yml](file:///c:/Users/yash5/Desktop/Projects/Aereo/cert-generator/docker-compose.yml) with health checks. This guarantees anyone evaluating or running the project can start the complete environment with a single `docker compose up` command without manual dependency installations or service management.

---

## Learning & Future Scope

With additional development time, valuable extensions to this architecture would include:
1. **Interactive Template Editor & Canvas**: A web UI for dynamically uploading template backgrounds, dragging bounding boxes, and mapping custom fonts and coordinate positions.
2. **Exponential Backoff & Task Retries**: Automatic Celery retries for transient failures (e.g. temporary disk I/O latency or network timeouts).
3. **Cloud Object Storage (AWS S3 / GCP Cloud Storage)**: Uploading generated PDFs directly to S3/GCS buckets with presigned URLs instead of relying on local volume mounts.
4. **Webhooks & Email Dispatch**: Outbound webhook alerts or automated email dispatch with attached certificates upon recipient completion.
5. **Rate Limiting & Authentication**: API key authentication and token-bucket rate limiting on the `/api/jobs/` submission endpoint to prevent queue flooding.

---

## Frontend

A dedicated React + TypeScript frontend built with Vite and Tailwind CSS is available in the [`frontend/`](file:///c:/Users/yash5/Desktop/Projects/Aereo/frontend) directory. It provides a clean donor ledger interface to record recipients, observe live generation progress, and download generated certificates individually or in bulk.

### Running the Frontend

> **Prerequisite**: Ensure the FastAPI backend is running separately at `http://localhost:8000`.

```bash
cd frontend
npm install
npm run dev
```

The frontend will run at: **`http://localhost:5173`**
