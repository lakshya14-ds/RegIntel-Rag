# RegIntel RAG — React + TypeScript + Vite Frontend

Modern, responsive, production-ready frontend for the **RegIntel RAG** Regulatory Intelligence & Change Detection Platform.

---

## 🚀 Features

- **Ask RegIntel (`/ask`)**: Grounded regulatory question answering with interactive citations (`[1]`, `[2]`), query interpretation breakdown, and side drawer evidence inspection.
- **Compare Regulations (`/compare`)**: 4-tier structural regulatory diff analysis classifying mandates into **ADDED**, **MODIFIED**, **REMOVED**, and **UNCHANGED** with side-by-side clause diff boxes and JSON report export.
- **Latest Regulations (`/latest`)**: Filterable catalog of indexed SEBI circulars, master directions, and regulatory gazettes.
- **Search Documents (`/search`)**: Direct multi-method candidate clause retrieval across BM25 keyword matching, dense vector search, and neural cross-encoder reranking.
- **Document Details (`/document/:documentId`)**: Metadata, circular numbering, effective dates, and authority sources.
- **Document Timeline (`/document/:documentId/timeline`)**: Chronological version lineage and supersession graph.
- **About & Metrics (`/about`)**: Architecture diagrams, pipeline descriptions, empirical benchmark metrics, and live system health.

---

## 🛠️ Technology Stack

- **Framework**: React 18
- **Language**: TypeScript 5.6 (Strict Mode)
- **Build Tool**: Vite 5.4
- **Routing**: React Router 6.28
- **Icons**: Lucide React
- **Testing**: Vitest + React Testing Library + JSDOM
- **Styling**: Pure Modular Design System with CSS variables and Inter typography
- **Containerization**: Multi-stage Docker (Node.js build -> Nginx static serving)

---

## 💻 Local Development

### 1. Install Dependencies
```bash
npm install
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default configuration:
```env
VITE_API_BASE_URL=http://localhost:8000
```

### 3. Start Development Server
```bash
npm run dev
```
The React frontend will be accessible at: `http://localhost:5173`

---

## 🧪 Testing & Validation

```bash
# Run TypeScript Typecheck
npm run typecheck

# Run ESLint validation
npm run lint

# Run Unit & Integration Tests (Vitest)
npm run test

# Build Production Assets
npm run build
```

---

## 🐳 Docker Deployment

The application is containerized with a multi-stage Docker build served via Nginx on port 80.

```bash
# Build frontend container
docker build -t regintel-frontend .

# Run with docker compose (from root)
docker compose up --build
```
