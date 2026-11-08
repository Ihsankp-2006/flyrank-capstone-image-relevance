# AI Image Understanding & Content Matching Engine
## System Design — Version 1.0

### 1. Problem Statement

The system automatically understands an image library, extracts structured information from images, and recommends relevant images for blog posts.

It must identify suitable images based on their actual content rather than filenames or exact keyword matches.

The system must also prevent incorrect recommendations. If an image does not satisfy the matching criteria, it should reject the candidate and explain why instead of returning an unreliable recommendation.

### 2. Technology Stack

- Language: Python 3
- Backend: FastAPI
- Vision AI: Google Gemini Flash
- Embeddings: Gemini Embeddings
- Database: PostgreSQL
- Similarity calculation: Cosine similarity
- Validation: Pydantic
- Background processing: Python background worker
- Version control: Git and GitHub

### 3. Data Model

**Images**
- id
- filename
- file_path
- category
- processing_status
- created_at

**Image Metadata**
- id
- image_id
- subject
- attributes
- caption
- confidence
- review_status

**Image Embeddings**
- id
- image_id
- embedding
- model_name

**Posts**
- id
- title
- content
- created_at

**Post Embeddings**
- id
- post_id
- embedding
- model_name

**Suggestions**
- id
- post_id
- image_id
- similarity_score
- guard_status
- explanation

**Reviews**
- id
- suggestion_id
- decision
- reviewed_at

PostgreSQL will store application data and embeddings. At the initial dataset scale, vector storage can use database arrays with cosine similarity calculated in Python. A dedicated vector extension can be considered later.

### 4. API Surface

Initial planned endpoints:

- POST /images/upload — Register an image for processing.
- POST /images/process — Trigger image understanding.
- GET /images — List available images and metadata.
- POST /posts — Create a blog post.
- GET /posts/{post_id}/images — Retrieve ranked image recommendations.
- POST /suggestions/{suggestion_id}/approve — Approve a suggestion.
- POST /suggestions/{suggestion_id}/reject — Reject a suggestion.
- GET /suggestions/{suggestion_id} — Inspect a suggestion and its explanation.
- GET /health — Check API health.

### 5. Architecture Overview

Image ingestion
    |
    v
Background Image Processing
    |
    v
Gemini Flash Vision Model
    |
    v
Structured Metadata
    |
    v
Pydantic Validation
    |
    v
Image Embedding Generation
    |
    v
PostgreSQL Storage

Blog Post
    |
    v
Post Embedding Generation
    |
    v
Similarity Ranking
    |
    v
Mismatch Guard
    |
    +---- Valid match ----> Ranked Image Suggestion
    |
    +---- Invalid match --> Rejection with Explanation

### 6. Mismatch Guard

The mismatch guard is the central reliability component.

It evaluates:
- Image and post category compatibility.
- Extracted subject and attributes.
- Semantic similarity score.
- Vision model confidence.
- Configurable acceptance thresholds.

The guard must reject unsuitable candidates and provide a human-readable explanation.

Example:

Post: The behavior of red foxes

Candidate: A gray wolf in the forest

Result: REJECTED

Reason: Animal category mismatch — expected fox, detected wolf.

The similarity thresholds will be tuned using a labeled evaluation dataset rather than selected arbitrarily.

### 7. Dataset and Evaluation

The initial image corpus will contain at least 40 licensed-free images across four or more categories.

The evaluation dataset will contain at least 10 blog posts, each associated with its correct image.

The main evaluation metric will be top-1 precision.

### 8. Explicit Non-Goal

This project will not build a public image-sharing platform or a full frontend application. Its focus is the backend image-understanding, semantic-matching, safety, and review system.

### 9. Reliability

- Validate every AI response against a defined schema.
- Flag low-confidence image classifications.
- Retry failed background processing safely.
- Track AI usage and cost per call.
- Reject unsuitable recommendations rather than guessing.
- Keep API keys and secrets in environment variables.

---

Project: FlyRank AI Image Understanding & Content Matching Engine
Design Version: 1.0

