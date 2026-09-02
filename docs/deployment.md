# Containerization & Deployment: Docker & Docker Compose

## 1. Overview
The RegIntel RAG stack is fully containerized for seamless multi-service orchestration with isolated environments for the FastAPI backend, React + TypeScript + Vite frontend (served via Nginx), MongoDB database, and MLflow tracking server.

---

## 2. Docker Architecture

```
                       HOST MACHINE
                            │
       ┌────────────────────┼────────────────────┐
       │:8000               │:5173               │:5000
       ▼                    ▼                    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  FastAPI     │◄────│  React/Vite  │     │  MLflow      │
│  Service     │     │  (Nginx)     │     │  Tracker     │
└──────┬───────┘     └──────────────┘     └──────┬───────┘
       │                                         │
       ▼                                         ▼
┌──────────────┐                          ┌──────────────┐
│  MongoDB     │                          │  SQLite DB   │
│  Data Store  │                          │  Artifacts   │
└──────────────┘                          └──────────────┘
```

---

## 3. Starting the Full Stack

### Build and Launch Services
```bash
docker compose up --build -d
```

### Checking Service Health
```bash
docker compose ps
```

### Accessing Endpoints
- **React Dashboard**: [http://localhost:5173](http://localhost:5173)
- **FastAPI REST Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **MLflow Tracking UI**: [http://localhost:5000](http://localhost:5000)

---

## 4. Verification Script
Run the automated deployment readiness check:
```bash
python scripts/verify_deployment.py
```
