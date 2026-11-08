# Database Design — Version 1.1

## Database
PostgreSQL with the pgvector extension.

## 1. Tables

### images
Stores original image information.
- id UUID PRIMARY KEY
- filename VARCHAR
- file_path TEXT
- processing_status VARCHAR
- created_at TIMESTAMP

### image_metadata
Stores information extracted from images by Gemini Flash.
- id UUID PRIMARY KEY
- image_id UUID FOREIGN KEY REFERENCES images(id), UNIQUE
- subject VARCHAR
- category VARCHAR
- attributes JSONB
- caption TEXT
- confidence FLOAT
- review_status VARCHAR
- embedding VECTOR(768)
- embedding_model VARCHAR
- created_at TIMESTAMP

### posts
Stores blog post content and its semantic representation.
- id UUID PRIMARY KEY
- title VARCHAR
- content TEXT
- embedding VECTOR(768)
- embedding_model VARCHAR
- created_at TIMESTAMP

### suggestions
Stores image recommendations and mismatch-guard decisions.
- id UUID PRIMARY KEY
- post_id UUID FOREIGN KEY REFERENCES posts(id)
- image_id UUID FOREIGN KEY REFERENCES images(id)
- similarity_score FLOAT
- guard_status VARCHAR
- explanation TEXT
- created_at TIMESTAMP

### reviews
Stores human decisions about suggestions.
- id UUID PRIMARY KEY
- suggestion_id UUID FOREIGN KEY REFERENCES suggestions(id)
- decision VARCHAR
- reviewed_at TIMESTAMP

### processing_jobs
Tracks background image-processing jobs.
- id UUID PRIMARY KEY
- image_id UUID FOREIGN KEY REFERENCES images(id)
- status VARCHAR
- attempts INTEGER
- max_attempts INTEGER
- error_message TEXT
- started_at TIMESTAMP
- completed_at TIMESTAMP
- created_at TIMESTAMP

### ai_usage_logs
Tracks individual AI operations and their estimated costs.
- id UUID PRIMARY KEY
- image_id UUID NULL FOREIGN KEY REFERENCES images(id)
- post_id UUID NULL FOREIGN KEY REFERENCES posts(id)
- operation VARCHAR
- model_name VARCHAR
- input_tokens INTEGER
- output_tokens INTEGER
- duration_ms INTEGER
- estimated_cost_usd NUMERIC
- created_at TIMESTAMP

## 2. Relationships

- One image has one metadata record.
- One image metadata record contains its image embedding.
- One post contains its post embedding.
- One post can have multiple image suggestions.
- One image can appear in multiple suggestions.
- One suggestion can have multiple reviews.
- One image can have multiple processing jobs.
- AI usage logs can optionally reference an image or a post.

## 3. Vector Search

- Image captions and blog post content are converted into embeddings.
- Both use the same embedding model and compatible vector dimensions.
- Embeddings are stored directly in image_metadata and posts.
- pgvector cosine distance operator: `<=>`
- Lower cosine distance indicates greater similarity.

Embedding model: gemini-embedding-2. Output dimensions: 768.

## 4. Indexing Strategy

- Primary-key indexes.
- Foreign-key indexes where appropriate.
- Index on images.processing_status.
- Index on processing_jobs.status.
- Indexes on suggestions.post_id and suggestions.image_id.
- Vector index on image_metadata.embedding.

The vector index type and parameters will be selected after testing the initial dataset.

## 5. Data Integrity

- UUID primary keys.
- Foreign-key constraints.
- NOT NULL constraints for required fields.
- UNIQUE constraint on image_metadata.image_id.
- CHECK constraints for valid status and decision values.
- Timestamps for tracking record creation and processing.

## 6. System Architecture

Image Upload
    -> Gemini Flash Vision Analysis
    -> Structured Metadata Validation
    -> Caption Embedding
    -> PostgreSQL + pgvector

Blog Post
    -> Post Embedding
    -> PostgreSQL + pgvector

Post Embedding + Image Embeddings
    -> Semantic Similarity Ranking
    -> Mismatch Guard
    -> Ranked Suggestions
    -> Human Review

