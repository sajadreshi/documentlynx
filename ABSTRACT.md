# DocumentLynx

## A Multi-Agent Platform for Automated Question Extraction and Management from Educational Documents

DocumentLynx is an end-to-end platform that automates the extraction, classification, and management of educational questions from uploaded documents such as exam papers and worksheets. The system employs a **multi-agent architecture** orchestrated by [LangGraph](https://github.com/langchain-ai/langgraph), where six specialized agents — *Ingestion*, *Parsing*, *Markdown Validation*, *Persistence*, *Classification*, and *Vectorization* — collaborate in a stateful pipeline to transform raw PDF documents into structured, searchable question banks.

### Document Processing Pipeline

Documents are uploaded to **Google Cloud Storage** and processed asynchronously through [IBM Docling](https://github.com/DS4SD/docling) for layout-aware parsing, preserving complex elements including mathematical formulas, tables, and embedded images. An LLM-powered extraction agent identifies individual questions from the parsed markdown, while a validation agent ensures structural correctness through an iterative feedback loop. Extracted questions are persisted in **PostgreSQL**, classified by type, difficulty, topic, and cognitive level, and embedded into a vector space using sentence transformers (**pgvector**) to enable semantic similarity search and deduplication.

### Backend Infrastructure

The backend is built on **FastAPI** with client-credential authentication (bcrypt-hashed secrets), and includes production-grade infrastructure:

- **Retry decorators** with exponential backoff on all LLM and external service calls
- **Circuit breaker pattern** for fault isolation
- **Typed exception hierarchies** for structured error handling
- **LangSmith tracing** (optional) for full pipeline observability
- **Evaluation framework** with baseline datasets for regression testing of extraction and classification quality

### Frontend

A **React + TypeScript** frontend provides:

- Drag-and-drop document upload with real-time pipeline status tracking
- Paginated document and question browser
- Split-pane question editor with a **CodeMirror** markdown editor and live preview with **KaTeX**-rendered mathematical notation
- Fully editable multiple-choice options and correct answers that persist back to their respective database fields

### Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python, FastAPI, LangGraph, LangChain |
| **Database** | PostgreSQL, pgvector |
| **Storage** | Google Cloud Storage |
| **Document Parsing** | IBM Docling |
| **LLM** | Groq (LLaMA 3.3 70B) |
| **Embeddings** | HuggingFace sentence-transformers |
| **Frontend** | React, Vite, TanStack Query, CodeMirror 6, KaTeX |
