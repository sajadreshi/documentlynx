"""Generate end-to-end flow diagram for DocumentLynx."""

import graphviz

dot = graphviz.Digraph(
    "DocumentLynx",
    format="png",
    engine="dot",
    graph_attr={
        "rankdir": "TB",
        "bgcolor": "#FAFBFC",
        "fontname": "Helvetica Neue",
        "pad": "0.8",
        "nodesep": "0.6",
        "ranksep": "0.8",
        "dpi": "200",
        "label": "DocumentLynx — End-to-End Flow Diagram",
        "labelloc": "t",
        "fontsize": "24",
        "fontcolor": "#1a1a2e",
    },
    node_attr={
        "fontname": "Helvetica Neue",
        "fontsize": "11",
        "style": "filled",
        "penwidth": "1.5",
    },
    edge_attr={
        "fontname": "Helvetica Neue",
        "fontsize": "9",
        "color": "#6B7280",
        "arrowsize": "0.8",
    },
)

# ── User / Frontend Layer ──
with dot.subgraph(name="cluster_frontend") as c:
    c.attr(
        label="Frontend (React + TypeScript)",
        style="rounded,filled",
        color="#3B82F6",
        fillcolor="#EFF6FF",
        fontcolor="#1E40AF",
        fontsize="13",
        fontname="Helvetica Neue Bold",
    )
    node = {"shape": "box", "fillcolor": "#DBEAFE", "color": "#3B82F6", "fontcolor": "#1E3A5F"}
    c.node("upload", "Upload Page\n(Drag & Drop)", **node)
    c.node("status", "Pipeline Status\nTracker", **node)
    c.node("doclist", "Documents\nBrowser", **node)
    c.node("docdetail", "Document Detail\n& Question List", **node)
    c.node("editor", "Question Editor\n(CodeMirror + KaTeX)", **node)

# ── API Layer ──
with dot.subgraph(name="cluster_api") as c:
    c.attr(
        label="Backend API (FastAPI)",
        style="rounded,filled",
        color="#8B5CF6",
        fillcolor="#F5F3FF",
        fontcolor="#5B21B6",
        fontsize="13",
        fontname="Helvetica Neue Bold",
    )
    node = {"shape": "box", "fillcolor": "#EDE9FE", "color": "#8B5CF6", "fontcolor": "#3B0764"}
    c.node("upload_api", "POST /upload\n(Multipart)", **node)
    c.node("process_api", "POST /process-doc\n(Async Job)", **node)
    c.node("job_api", "GET /jobs/{id}\n(Status Poll)", **node)
    c.node("doc_api", "GET /documents\nGET /documents/{id}", **node)
    c.node("q_api", "GET /questions/{id}\nPUT /questions/{id}", **node)
    c.node("auth", "Authentication\n(X-Client-Id / Secret)", shape="diamond", fillcolor="#DDD6FE", color="#7C3AED", fontcolor="#3B0764")

# ── Agent Pipeline ──
with dot.subgraph(name="cluster_pipeline") as c:
    c.attr(
        label="Multi-Agent Pipeline (LangGraph)",
        style="rounded,filled",
        color="#059669",
        fillcolor="#ECFDF5",
        fontcolor="#065F46",
        fontsize="13",
        fontname="Helvetica Neue Bold",
    )
    agent = {"shape": "box", "fillcolor": "#D1FAE5", "color": "#059669", "fontcolor": "#064E3B"}
    c.node("ingestion", "1. Ingestion Agent\n• Detect file format\n• Store in GCS\n• Create job record", **agent)
    c.node("parsing", "2. Parsing Agent\n• IBM Docling\n• Layout-aware conversion\n• Preserve formulas & images", **agent)
    c.node("validation", "3. Validation Agent\n• Check markdown structure\n• Verify completeness\n• LLM-assisted review", **agent)
    c.node("persistence", "4. Persistence Agent\n• LLM question extraction\n• Store in PostgreSQL\n• Link to document", **agent)
    c.node("classification", "5. Classification Agent\n• Type, topic, difficulty\n• Cognitive level\n• Grade level", **agent)
    c.node("vectorization", "6. Vectorization Agent\n• Generate embeddings\n• Deduplication check\n• Store in pgvector", **agent)

# ── Validation loop ──
    c.edge("validation", "parsing", label="  Retry\n  (max 3x)", style="dashed", color="#DC2626", fontcolor="#DC2626", constraint="false")

# ── Data Layer ──
with dot.subgraph(name="cluster_data") as c:
    c.attr(
        label="Data Layer",
        style="rounded,filled",
        color="#D97706",
        fillcolor="#FFFBEB",
        fontcolor="#92400E",
        fontsize="13",
        fontname="Helvetica Neue Bold",
    )
    db = {"shape": "cylinder", "fillcolor": "#FDE68A", "color": "#D97706", "fontcolor": "#78350F"}
    c.node("postgres", "PostgreSQL\n• Documents\n• Questions\n• Jobs\n• Metadata", **db)
    c.node("pgvector", "pgvector\n• Embeddings\n• Similarity Search", **db)
    c.node("gcs", "Google Cloud\nStorage\n• PDFs\n• Images", **db)

# ── External Services ──
with dot.subgraph(name="cluster_external") as c:
    c.attr(
        label="External Services",
        style="rounded,filled",
        color="#EC4899",
        fillcolor="#FDF2F8",
        fontcolor="#9D174D",
        fontsize="13",
        fontname="Helvetica Neue Bold",
    )
    ext = {"shape": "box", "fillcolor": "#FCE7F3", "color": "#EC4899", "fontcolor": "#831843", "style": "filled,rounded"}
    c.node("docling", "IBM Docling\n(Document Parser)", **ext)
    c.node("groq", "Groq API\n(LLaMA 3.3 70B)", **ext)
    c.node("hf", "HuggingFace\n(MiniLM-L6-v2)", **ext)
    c.node("langsmith", "LangSmith\n(Observability)", **ext)

# ── Edges: Frontend → API ──
dot.edge("upload", "upload_api", label="  File + user_id")
dot.edge("upload", "process_api", label="  document_url")
dot.edge("status", "job_api", label="  Poll every 3s")
dot.edge("doclist", "doc_api")
dot.edge("docdetail", "doc_api")
dot.edge("docdetail", "q_api")
dot.edge("editor", "q_api", label="  Edit & Save")

# ── Edges: Auth ──
dot.edge("auth", "upload_api", style="dotted", color="#7C3AED", arrowhead="none")
dot.edge("auth", "process_api", style="dotted", color="#7C3AED", arrowhead="none")
dot.edge("auth", "doc_api", style="dotted", color="#7C3AED", arrowhead="none")
dot.edge("auth", "q_api", style="dotted", color="#7C3AED", arrowhead="none")

# ── Edges: API → Pipeline ──
dot.edge("process_api", "ingestion", label="  Trigger pipeline", color="#059669", fontcolor="#059669")

# ── Edges: Pipeline internal ──
dot.edge("ingestion", "parsing", color="#059669")
dot.edge("parsing", "validation", color="#059669")
dot.edge("validation", "persistence", label="  Valid ✓", color="#059669", fontcolor="#059669")
dot.edge("persistence", "classification", color="#059669")
dot.edge("classification", "vectorization", color="#059669")

# ── Edges: Pipeline → Data ──
dot.edge("ingestion", "gcs", label="  Store PDF", style="dashed", color="#D97706")
dot.edge("persistence", "postgres", label="  Save questions", style="dashed", color="#D97706")
dot.edge("vectorization", "pgvector", label="  Store vectors", style="dashed", color="#D97706")

# ── Edges: Pipeline → External ──
dot.edge("parsing", "docling", label="  Parse", style="dashed", color="#EC4899")
dot.edge("persistence", "groq", label="  Extract", style="dashed", color="#EC4899")
dot.edge("classification", "groq", label="  Classify", style="dashed", color="#EC4899")
dot.edge("validation", "groq", label="  Validate", style="dashed", color="#EC4899")
dot.edge("vectorization", "hf", label="  Embed", style="dashed", color="#EC4899")

# ── Edges: API → Data (read path) ──
dot.edge("doc_api", "postgres", style="dashed", color="#D97706")
dot.edge("q_api", "postgres", style="dashed", color="#D97706")
dot.edge("job_api", "postgres", style="dashed", color="#D97706")

# ── Observability (subtle) ──
dot.edge("ingestion", "langsmith", style="dotted", color="#EC489966", arrowhead="none")
dot.edge("vectorization", "langsmith", style="dotted", color="#EC489966", arrowhead="none")

# ── Render ──
output_path = dot.render("/Users/sajad/documentlynx/docs/documentlynx-flow", cleanup=True)
print(f"Generated: {output_path}")
