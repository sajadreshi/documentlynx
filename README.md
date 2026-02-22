# DocumentLynx

A multi-agent platform for automated question extraction and management from educational documents.

DocumentLynx processes PDF exam papers and worksheets through a six-stage AI pipeline — parsing, validation, extraction, persistence, classification, and vectorization — to produce structured, searchable question banks with a web-based editing interface.

## Architecture

![End-to-End Flow](docs/documentlynx-flow.png)

**Processing Pipeline** — Six LangGraph agents operate in sequence:

| Stage | Agent | What it does |
|-------|-------|-------------|
| 1 | Ingestion | Accepts upload, stores PDF in GCS, creates job |
| 2 | Parsing | IBM Docling converts PDF to Markdown (preserves formulas, tables, images) |
| 3 | Validation | LLM checks structural correctness, retries up to 3x |
| 4 | Persistence | LLM extracts individual questions, stores in PostgreSQL |
| 5 | Classification | LLM classifies by type, topic, difficulty, cognitive level |
| 6 | Vectorization | Generates embeddings, stores in pgvector for semantic search |

**Frontend** — React app with document upload, real-time status tracking, question browser, and split-pane Markdown editor with live KaTeX math preview.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python, FastAPI, LangGraph, LangChain |
| Database | PostgreSQL 15+ with pgvector |
| Storage | Google Cloud Storage |
| Document Parsing | IBM Docling |
| LLM | Groq (LLaMA 3.3 70B) |
| Embeddings | HuggingFace sentence-transformers (all-MiniLM-L6-v2) |
| Frontend | React 19, TypeScript, Vite, TanStack Query, CodeMirror 6, KaTeX |
| Observability | LangSmith (optional) |

## Prerequisites

- Python 3.8+
- Node.js 18+
- PostgreSQL 15+ with [pgvector](https://github.com/pgvector/pgvector) extension
- Google Cloud service account with Storage Object Admin role
- [Groq API key](https://console.groq.com) (free tier available)
- [IBM Docling](https://github.com/DS4SD/docling) running on port 5001

## Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/sajadreshi/documentlynx.git
cd documentlynx
cp .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/documently
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_CLOUD_STORAGE_BUCKET=your-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
GROQ_API_KEY=your-groq-api-key
```

### 2. Database

```bash
createdb documently
psql -d documently -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 3. Backend

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.scripts.init_db
python -m app.scripts.manage_clients create dev-client dev-secret
uvicorn app.main:app --reload --port 8000
```

Backend runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

### 4. Frontend

Open a new terminal:

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```env
VITE_API_URL=http://localhost:8000
VITE_CLIENT_ID=dev-client
VITE_CLIENT_SECRET=dev-secret
```

```bash
npm run dev
```

Frontend runs at `http://localhost:5173`.

### 5. Docling (Document Parser)

```bash
docker run -p 5001:5001 ds4sd/docling-serve
```

### 6. Verify

1. Open `http://localhost:5173`
2. Upload a PDF document
3. Watch the pipeline process through all 6 stages
4. Browse extracted questions and edit them in the split-pane editor

## API Endpoints

All endpoints require `X-Client-Id` and `X-Client-Secret` headers.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/documently/api/v1/upload` | Upload a document (multipart) |
| `POST` | `/documently/api/v1/process-doc` | Trigger async processing pipeline |
| `GET` | `/documently/api/v1/jobs/{id}` | Poll job status |
| `GET` | `/documently/api/v1/documents` | List documents (paginated) |
| `GET` | `/documently/api/v1/documents/{id}` | Document detail |
| `GET` | `/documently/api/v1/documents/{id}/questions` | List questions (paginated) |
| `GET` | `/documently/api/v1/documents/{id}/questions/{qid}` | Question detail |
| `PUT` | `/documently/api/v1/documents/{id}/questions/{qid}` | Update question, options, correct answer |
| `GET` | `/health/detailed` | Health check (database, GCS, Docling) |

## Client Management

```bash
python -m app.scripts.manage_clients create <client_id> <secret>
python -m app.scripts.manage_clients list
python -m app.scripts.manage_clients activate <client_id>
python -m app.scripts.manage_clients deactivate <client_id>
python -m app.scripts.manage_clients delete <client_id>
```

## Running Tests

```bash
pytest tests/ -v
```

## Running Evaluations

```bash
# Mock mode (no LLM calls)
python run_evals.py --mode mock --agent all

# Live mode (requires Groq API key)
python run_evals.py --mode live --agent extraction --output eval_results.json
```

## Project Structure

```
documentlynx/
├── app/
│   ├── main.py                 # FastAPI application & startup
│   ├── config.py               # Pydantic settings
│   ├── database.py             # SQLAlchemy connection
│   ├── models.py               # ORM models (Document, Question, Job)
│   ├── auth.py                 # Client credential authentication
│   ├── api_routes.py           # Upload & processing endpoints
│   ├── question_routes.py      # Document & question CRUD endpoints
│   ├── exceptions.py           # Typed exception hierarchy
│   ├── retry.py                # Exponential backoff decorator
│   ├── circuit_breaker.py      # Circuit breaker pattern
│   ├── observability.py        # LangSmith @traceable wrapper
│   ├── agents/                 # LangGraph agents (6 pipeline stages)
│   ├── services/               # Business logic (storage, embedding, orchestrator)
│   ├── tools/                  # Classification, search, JSON parsing tools
│   ├── evaluation/             # Evaluation harness & baseline datasets
│   └── scripts/                # DB init, client management
├── frontend/
│   ├── src/
│   │   ├── pages/              # Upload, Documents, Detail, QuestionEdit
│   │   ├── components/         # Dropzone, StatusTracker, Editor, Preview
│   │   ├── hooks/              # Job polling, unsaved changes
│   │   └── api/                # Axios client & API functions
│   └── package.json
├── tests/                      # pytest test suite
├── prompts/                    # YAML prompt templates
├── docs/                       # Architecture diagrams
├── requirements.txt
├── .env.example
└── README.md
```

## Security

- Client secrets are bcrypt-hashed in PostgreSQL
- Never commit `.env` or credential files
- CORS configured for localhost development; restrict in production
- Use HTTPS in production environments

## License

This project is provided as-is for use in your applications.
