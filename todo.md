# Todo List

- [ ] **Phase 1: Project setup and architecture planning**
  - [ ] Create project directory structure
  - [ ] Initialize git repository
  - [ ] Set up virtual environment

- [ ] **Phase 2: Backend API development with FastAPI**
  - [ ] Set up FastAPI project
  - [ ] Implement basic API endpoints
  - [ ] Integrate LLM backend (Groq API/Ollama)

- [ ] **Phase 3: Agent orchestrator implementation**
  - [ ] Design orchestrator logic (Plan -> Retrieve -> Act -> Verify -> Respond)
  - [ ] Implement deterministic halting
  - [ ] Implement JSON schema enforced outputs

- [ ] **Phase 4: RAG system and memory implementation**
  - [ ] Set up short-term memory (in-memory)
  - [ ] Set up long-term memory (Postgres + pgvector/Qdrant)
  - [ ] Implement hybrid search (embeddings + keyword fallback)

- [ ] **Phase 5: Basic connectors and tools**
  - [ ] Implement Web search (DuckDuckGo API/scraper)
  - [ ] Implement Email connector (Gmail API)
  - [ ] Implement Slack/Discord bots (basic integration)
  - [ ] Implement Google Drive/Notion API (read docs)
  - [ ] Implement basic guardrails (allow/deny tool list, PII redaction, toxicity filter)

- [ ] **Phase 6: Simple frontend UI**
  - [ ] Set up React + Tailwind project
  - [ ] Design chat UI
  - [ ] Implement multi-tenant branding/settings

- [ ] **Phase 7: Testing and deployment setup**
  - [ ] Write unit and integration tests
  - [ ] Set up Docker for containerization
  - [ ] Configure deployment to free tier hosting (Railway, Render, Fly.io, or Vercel)

- [ ] **Phase 8: Documentation and delivery**
  - [ ] Write SOW template
  - [ ] Write runbook
  - [ ] Deliver project and documentation to user

```Folder Structure
ai-agent-platform/
├── .github/                  # CI/CD workflows
│   └── workflows/
│       └── ci-cd.yml         # GitHub Actions for CI/CD
├── docker/                   # Infra configs
│   ├── Dockerfile            # For backend
│   ├── docker-compose.yml    # For local dev (Postgres, etc.)
│   └── .env.example          # Env vars template
├── src/                      # Main source code
│   ├── api/                  # API Layer (FastAPI)
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI app entry
│   │   ├── routes.py         # Endpoints
│   │   ├── auth.py           # Auth logic
│   │   └── middleware.py     # Multi-tenant routing
│   ├── orchestrator/         # Agent Orchestrator
│   │   ├── __init__.py
│   │   ├── graph_dsl.py      # Graph DSL implementation
│   │   ├── executor.py       # Plan/Retrieve/Act/Verify loop with halting/retries
│   │   └── schemas.py        # JSON schemas
│   ├── rag/                  # RAG components
│   │   ├── __init__.py
│   │   ├── ingestion.py      # Ingestion pipeline
│   │   ├── search.py         # Hybrid search + reranker
│   │   └── citation.py       # Citation enforcement
│   ├── connectors/           # Plug-and-play connectors
│   │   ├── __init__.py
│   │   ├── email.py          # Gmail API
│   │   ├── slack.py          # Slack bot
│   │   ├── hubspot.py        # HubSpot CRM
│   │   ├── zendesk.py        # Zendesk Helpdesk
│   │   └── calendar.py       # Google Calendar API
│   ├── guardrails/           # Guardrails
│   │   ├── __init__.py
│   │   ├── pii_redaction.py  # PII redaction
│   │   ├── allowlist.py      # Allow/deny lists
│   │   └── policy_checks.py  # Policy enforcement
│   ├── hitl/                 # Human-in-the-Loop
│   │   ├── __init__.py
│   │   ├── review_queue.py   # Review queue logic
│   │   └── learning.py       # Learning from edits
│   ├── memory/               # Memory layers
│   │   ├── __init__.py
│   │   ├── short_term.py     # In-memory session
│   │   └── long_term.py      # Postgres/pgvector
│   ├── llm/                  # LLM Backend
│   │   ├── __init__.py
│   │   ├── groq.py           # Groq API integration
│   │   └── ollama.py         # Ollama fallback
│   ├── observability/        # Logging and tracking
│   │   ├── __init__.py
│   │   └── logger.py         # Postgres logging
│   └── utils/                # Shared utils
│       ├── __init__.py
│       └── config.py         # Env config loader
├── templates/                # Three templates
│   ├── template1/            # e.g., Customer Support Agent
│   │   ├── prompts.json      # Versioned prompts
│   │   └── golden_set.json   # Golden Q&A sets
│   ├── template2/            # e.g., Sales Assistant
│   │   ├── prompts.json
│   │   └── golden_set.json
│   └── template3/            # e.g., Personal Scheduler
│       ├── prompts.json
│       └── golden_set.json
├── frontend/                 # Optional React UI (setup separately)
│   ├── src/
│   │   └── App.js            # Basic chat UI
│   └── package.json          # With React, Tailwind
├── docs/                     # Documentation
│   ├── sow_template.md       # Statement of Work template
│   └── runbook.md            # Operations runbook
├── tests/                    # Unit/integration tests
│   └── test_orchestrator.py  # Example test
├── requirements.txt          # Python deps
├── pyproject.toml            # For packaging/build
├── README.md                 # Project overview
├── .gitignore                # Git ignores
└── setup.py                  # For packaging templates
```