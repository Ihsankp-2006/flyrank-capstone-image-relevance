# Build Log

This log records the use of AI-assisted development tools during the FlyRank capstone.

## Development assistance

AI assistance was used during implementation, debugging, code review, test development, and documentation preparation.

Tools used:
- ChatGPT
- GitHub Copilot

## Areas where AI assistance was used

- FastAPI backend structure and API implementation.
- Database models, SQLAlchemy integration, and Alembic migrations.
- Image and post service logic.
- Background processing and retry infrastructure.
- Evaluation dataset import tooling.
- Automated test development and debugging.
- Docker and Docker Compose configuration.
- Final offline verification and submission documentation.

## Review and corrections

Generated code and recommendations were reviewed rather than accepted blindly.

The development process included:
- Running the automated test suite.
- Checking Python compilation.
- Checking Alembic migration consistency.
- Validating Docker Compose configuration.
- Verifying API availability.
- Checking dataset identifiers, labels, mappings, and checksums.
- Checking repository hygiene and secret exposure.

## AI execution policy

Gemini API calls were intentionally not made during this project completion stage.

No live vision inference or embedding generation was performed. The database therefore contains pending image records and posts without embeddings.

## Final verification

The final offline verification recorded:
- 62 passing tests.
- Successful Python compilation.
- Successful Alembic consistency check.
- Successful Docker Compose configuration validation.
- HTTP 200 responses from the health and OpenAPI endpoints.
- 40 validated evaluation images and 10 approved evaluation posts.

## Limitations

The AI-generated outputs and semantic matching quality have not been validated using live model calls. No top-1 precision result is claimed.

The developer remains responsible for understanding, reviewing, and explaining the submitted implementation.