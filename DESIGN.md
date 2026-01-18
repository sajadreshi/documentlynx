# Multi-Agent Document Question Extraction & Vectorization Platform

## System Architecture Overview

The system uses a multi-agent architecture orchestrated by LangGraph to process documents, extract questions, validate Markdown, and store vectorized questions.

## Agent Responsibilities

### 1. Ingestion Agent
- Accept document upload
- Detect file format (PDF, DOCX, XLSX, images, scanned files)
- Store document in GCS
- Create extraction job record
- Return job_id immediately (async workflow)

### 2. Parsing Agent
- Select appropriate parser based on file type
- Use IBM Docling for complex layouts
- Generate initial Markdown preserving tables, images, formulas, chemistry symbols
- Maintain question numbering

### 3. Question Extraction Agent
- Analyze parsed Markdown content
- Identify actual questions using LLM
- Filter out headers, footers, instructions, watermarks
- Extract questions with context preservation

### 4. Markdown Validation Agent
- Validate Markdown syntax and structure
- Check formatting correctness
- Flag malformed content
- Loop back to Parsing Agent if validation fails (max 3 iterations)

### 5. Vectorization Agent
- Generate embeddings for each extracted question
- Check for duplicates (cosine similarity threshold)
- Upsert to Qdrant (overwrite existing vectors)
- Store embedding metadata

### 6. Persistence Agent
- Store questions in PostgreSQL with user association
- Store metadata (source document, page number, question type)
- Link questions to extraction job
- Update job status

## Database Schema

### New Models

**User Model:**
- id (String, primary key) - user_id from existing system
- email (String, optional)
- created_at, updated_at (timestamps)

**ExtractionJob Model:**
- id (UUID, primary key)
- user_id (String, foreign key)
- document_url (String)
- document_filename (String)
- status (String) - pending, processing, completed, failed
- created_at, completed_at (timestamps)
- error_message (Text, optional)
- metadata (JSONB)

**ExtractedQuestion Model:**
- id (Integer, primary key)
- job_id (String, foreign key)
- user_id (String, foreign key)
- question_text (Text)
- question_number (String, optional)
- page_number (Integer, optional)
- question_type (String, optional)
- markdown_content (Text)
- vector_id (String, optional) - Qdrant vector ID
- metadata (JSONB)
- created_at (timestamp)

## Technology Stack

- **Vector Database:** Qdrant (open-source)
- **Embedding Model:** OpenAI text-embedding-3-small
- **Document Parsing:** IBM Docling (primary), python-docx, openpyxl, pytesseract
- **Orchestration:** LangGraph
- **LLM Integration:** LangChain
- **Observability:** LangSmith
- **Background Tasks:** Celery or FastAPI BackgroundTasks

## Workflow

1. User uploads document → Ingestion Agent creates job
2. Parsing Agent processes document → generates Markdown
3. Question Extraction Agent identifies questions
4. Markdown Validation Agent validates → loops back if needed
5. Vectorization Agent creates embeddings → stores in Qdrant
6. Persistence Agent saves to database → updates job status

## API Endpoints

- `POST /documently/api/v1/extract-questions` - Trigger extraction (async)
- `GET /documently/api/v1/extraction-status/{job_id}` - Check job status
- `GET /documently/api/v1/questions` - List user's extracted questions
- `GET /documently/api/v1/questions/{question_id}` - Get specific question
- `POST /documently/api/v1/questions/search` - Semantic search questions

## Production Considerations

- Cost optimization: caching, batch processing
- Scalability: Celery workers, Qdrant clustering
- Observability: LangSmith tracing, structured logging
- Failure handling: retries, dead letter queue
- Idempotency: document hash + user_id as unique key

