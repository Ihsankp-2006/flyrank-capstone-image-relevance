# FlyRank AI Image Understanding & Content Matching Engine

A backend capstone project for the FlyRank AI Internship. The system provides image ingestion, post management, background processing infrastructure, image suggestions, and a human-review workflow using FastAPI and PostgreSQL.

## Project status

The backend structure, database models, offline evaluation dataset, and automated tests are in place.

**Important:** Live AI processing has intentionally not been run. Gemini API calls were not made. Images are currently pending processing, and posts do not yet have embeddings. Therefore, real semantic matching quality and top-1 precision have not been measured.

## Technology stack

- Python 3
- FastAPI
- SQLAlchemy
- PostgreSQL with pgvector support
- Alembic migrations
- Docker Compose
- Pytest

## Architecture

```text
                  Client
                    |
                    v
               FastAPI API
                    |
          +---------+---------+
          |                   |
          v                   v
     Image Service       Post Service
          |                   |
          v                   v
     PostgreSQL <------> Matching / Review Services
          |
          v
     Processing Jobs
          |
          v
      Background Worker
          |
          v
     Vision / Embedding Providers
       (AI execution not yet run)
```

The application separates HTTP routes, schemas, services, database models, and background workers.

## Main capabilities

- Image upload, listing, detail, status, and deletion endpoints.
- Post creation and retrieval.
- Background image-processing job infrastructure with retry handling.
- Image metadata and embedding integration points.
- Image suggestion and human-review API endpoints.
- Offline import of the labeled evaluation dataset.
- Automated tests for backend behavior.

## Requirements

- Python 3
- Docker Desktop with Docker Compose
- Git

## Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/Ihsankp-2006/flyrank-capstone-image-relevance.git
   cd flyrank-capstone-image-relevance
   ```

2. Create your environment file from the example:

   ```powershell
   Copy-Item .env.example .env
   ```

   Fill in the required local PostgreSQL configuration. Keep real credentials in `.env`; never commit it.

   Docker Compose services connect to PostgreSQL using `POSTGRES_HOST=db` and
   the container port. Commands run directly from Windows, such as the offline
   dataset importer, must instead use `POSTGRES_HOST=127.0.0.1` and the
   PostgreSQL port published by Docker Compose. Set these values only in the
   current PowerShell session so credentials remain in `.env` and the Docker
   configuration is unchanged:

   ```powershell
   $env:POSTGRES_HOST = "127.0.0.1"
   $env:POSTGRES_PORT = "<published PostgreSQL port>"
   ```

   Use the published port shown by `docker compose ps`, and remove the
   session-only overrides when finished:

   ```powershell
   Remove-Item Env:POSTGRES_HOST
   Remove-Item Env:POSTGRES_PORT
   ```

3. Start the services:

   ```bash
   docker compose up -d
   ```

4. Import the offline evaluation dataset:

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.import_evaluation_dataset
   ```

   The Python environment and dependencies must be installed before running this command.

5. Open the API documentation:

   - Swagger UI: `http://localhost:8000/docs`
   - OpenAPI schema: `http://localhost:8000/openapi.json`
   - Health check: `http://localhost:8000/health`

## Tests

Run the test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The final offline verification recorded **62 passing tests**.

## API endpoints

| Method | Endpoint |
|---|---|
| GET | `/` |
| GET | `/health` |
| GET | `/api/images/` |
| POST | `/api/images/upload` |
| POST | `/api/images/process` |
| GET | `/api/images/{image_id}` |
| DELETE | `/api/images/{image_id}` |
| GET | `/api/images/{image_id}/status` |
| POST | `/api/posts/` |
| GET | `/api/posts/{post_id}` |
| POST | `/api/posts/{post_id}/suggestions` |
| GET | `/api/posts/{post_id}/suggestions` |
| GET | `/api/suggestions/{suggestion_id}` |
| POST | `/api/suggestions/{suggestion_id}/approve` |
| POST | `/api/suggestions/{suggestion_id}/reject` |

See `/docs` for request and response schemas.

## Evaluation dataset

The offline evaluation dataset contains:

- 40 images across four categories.
- 10 evaluation posts.
- Human-approved image labels.
- Human-approved post-to-image reference mappings.
- Image provenance and SHA-256 checksums.

The dataset has been imported into the database. These approved mappings are ground-truth labels, not model-generated predictions.

## Verification results

The final offline verification recorded:

- 62 tests passed.
- Python compilation passed.
- Alembic migration check passed.
- Docker Compose configuration passed.
- API health and OpenAPI endpoints returned HTTP 200.
- 40 images and 10 posts were present in the database.
- No Gemini API calls were made.

## Limitations

- Gemini vision processing has not been executed.
- Image records remain pending processing.
- Post embeddings have not been generated.
- AI-generated semantic ranking and mismatch-guard behavior have not been evaluated against live model outputs.
- Top-1 precision is **not measured** and is intentionally not reported.
- The project should be treated as an implemented backend foundation with an offline-verified dataset and an unexecuted AI-processing stage.

## Security

- Store credentials in `.env`.
- Do not commit `.env`, API keys, or passwords.
- Use `.env.example` only for safe placeholder configuration.

## Repository

[GitHub – flyrank-capstone-image-relevance](https://github.com/Ihsankp-2006/flyrank-capstone-image-relevance)