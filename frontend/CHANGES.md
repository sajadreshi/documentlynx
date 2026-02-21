# Frontend Changes

## Setup

### Prerequisites

- Node.js >= 18
- npm >= 9

### Install & Run

```bash
cd frontend
npm install
npm run dev
```

The dev server starts at `http://localhost:5173`.

### Environment Variables

Create `frontend/.env`:

```
VITE_API_URL=http://localhost:8000
VITE_CLIENT_ID=dev-client
VITE_CLIENT_SECRET=<your-secret>
```

### Dependencies

| Package | Purpose |
|---------|---------|
| `react` + `react-dom` | UI framework |
| `react-router-dom` | Client-side routing |
| `@tanstack/react-query` | Server state, caching, polling |
| `axios` | HTTP client with auth interceptor |
| `react-dropzone` | Drag-and-drop file upload |
| `react-hot-toast` | Toast notifications |
| `@codemirror/lang-markdown` | Markdown editor |
| `@codemirror/view` + `@codemirror/state` | CodeMirror 6 core |
| `react-markdown` | Markdown rendering |
| `remark-math` + `rehype-katex` + `katex` | LaTeX math rendering |
| `tailwindcss` + `@tailwindcss/vite` | Styling |

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | UploadPage | Drag-and-drop PDF upload with job status tracking |
| `/documents` | DocumentsPage | Paginated list of processed documents |
| `/documents/:id` | DocumentDetailPage | Document info + question list |
| `/documents/:id/questions/:qid` | QuestionEditPage | Split-pane markdown editor with live preview |

## Features

- **Upload flow**: Drag PDF → upload to GCS → start processing → poll job status → review questions
- **Job status tracker**: Horizontal stepper showing all 8 pipeline stages with live polling
- **Question editor**: CodeMirror 6 with markdown syntax highlighting + live KaTeX preview
- **Keyboard shortcuts**: `Ctrl+S`/`Cmd+S` to save, `Alt+←`/`Alt+→` to navigate between questions
- **Unsaved changes warning**: `beforeunload` event + react-router navigation blocker
- **Responsive**: Split pane stacks vertically on screens < 768px
