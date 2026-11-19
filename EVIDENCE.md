# EVIDENCE.md

# Verification Evidence

This document records the verification results for the **FlyRank AI Image Understanding & Content Matching Engine**. It summarizes automated testing, infrastructure checks, dataset validation, database import verification, and the current status of AI-dependent functionality.

## 1. Automated Test Suite

**Status: PASS**

Command:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Result:
```text
62 passed
```

All 62 automated tests completed successfully.

## 2. Python Compilation

**Status: PASS**

Command:
```powershell
.\.venv\Scripts\python.exe -m compileall -q app scripts tests
```

Result:
```text
compileall=PASS
```

All application, script, and test modules passed Python compilation checks.

## 3. Database Migration Consistency

**Status: PASS**

Command:
```powershell
.\.venv\Scripts\alembic.exe check
```

Result:
```text
No new upgrade operations detected.
```

The SQLAlchemy models and existing Alembic migrations were consistent at the time of verification.

## 4. Docker Compose Configuration

**Status: PASS**

Command:
```powershell
docker compose config --quiet
```

Result:
```text
compose_config=PASS
```

The Docker Compose configuration was validated successfully. During verification, PostgreSQL was reported healthy and the background worker was running.

## 5. API Availability

**Status: PASS**

The following endpoints were checked:

| Endpoint | Result |
|---|---|
| `GET /health` | HTTP 200 |
| `GET /openapi.json` | HTTP 200 |

The FastAPI application responded successfully, and its OpenAPI schema exposed the registered application routes.

## 6. Evaluation Dataset Validation

**Status: PASS**

The offline evaluation dataset passed the recorded validation checks.

| Validation | Result |
|---|---:|
| Total images | 40 |
| Categories | 4 |
| Images per category | 10 |
| Evaluation posts | 10 |
| Approved image labels | 40/40 |
| Approved post-image mappings | 10/10 |
| Mapping ID validation | PASS |
| Image checksum verification | PASS |
| Manifest label verification | `true` |

The dataset contains four categories: wildlife, food, technology, and travel.

Image labels and post-image mappings were manually reviewed and approved. The manifest records this approval through `labels_verified: true`.

## 7. Database Import and Idempotency

**Status: PASS**

The evaluation dataset was imported through the offline import workflow.

Database counts after import:

```text
posts=10
images=40
processing_jobs=0
ai_usage_logs=0
unembedded_posts=10
pending_images=40
```

The import command was executed again to verify idempotency. Existing records were skipped rather than duplicated.

The absence of processing jobs, AI usage logs, and generated embeddings is expected because the dataset was imported without executing AI processing.

## 8. Security and Repository Hygiene

**Status: PASS**

The following checks were recorded:

- `.env` is excluded through `.gitignore`.
- `.env` is not tracked by Git.
- No matching hardcoded API-key or private-key patterns were found outside `.env`.
- `git diff --check` reported no whitespace errors.
- No Git history or repository upload operations were performed during verification.

## 9. AI Processing and Matching Evaluation

**Status: NOT RUN**

AI-dependent evaluation was intentionally not executed. No Gemini API calls were made during this verification stage.

As a result, the following capabilities have not yet been empirically evaluated:

- Vision-based metadata generation on the evaluation images.
- Image and blog-post embedding generation.
- Live semantic similarity ranking.
- Mismatch-guard acceptance and rejection probes using model-generated metadata.
- Top-1 matching precision.

The application includes the corresponding implementation components, but their live AI behavior and matching quality have not been established through this evaluation.

**No AI accuracy, precision, or matching-quality score is claimed.**

## 10. Verification Scope and Limitations

The backend passed the recorded automated tests, compilation checks, database migration checks, infrastructure configuration checks, API availability checks, and offline dataset validation.

The evaluation dataset and its approved labels were successfully imported into the database without invoking external AI services.

However, AI-dependent processing and matching acceptance tests remain unverified. They were intentionally excluded from this verification run to avoid external API usage and potential provider costs or usage-limit constraints.

Therefore, the current evidence demonstrates the verified backend foundation and offline evaluation workflow, rather than a completed measurement of live AI matching performance.

---

**Overall verification status:** Backend and offline verification passed; AI-dependent evaluation remains pending.