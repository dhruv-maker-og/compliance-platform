# ComplianceRewind & Policy Enforcer

A continuous compliance platform that combines **automated evidence collection** with **policy-as-code enforcement**, orchestrated by a GitHub Copilot CLI SDK agent.

## Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│                  React SPA (Fluent UI)                │
│  Dashboard │ Evidence Collection │ Policy │ Reports   │
└──────────────────┬───────────────────────────────────┘
                   │ SSE / REST
┌──────────────────▼───────────────────────────────────┐
│              FastAPI Backend (Python 3.12+)           │
│  ┌─────────────────────────────────────────────────┐ │
│  │         GitHub Copilot CLI SDK Agent             │ │
│  │  Skills: PCI-DSS, SOC2, Policy Enforcement      │ │
│  │  Tools: Evidence Assembler, Gap Analyzer,        │ │
│  │         OPA Tester, Report Generator             │ │
│  └──────────────┬──────────────────────────────────┘ │
│                  │ MCP Protocol                      │
│  ┌──────────────▼──────────────────────────────────┐ │
│  │  MCP Servers: Azure, GitHub, Entra ID, Purview  │ │
│  └─────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

## Key Features

- **Evidence Collection** — Automated gathering of compliance evidence from Azure, GitHub, Entra ID, and Purview via MCP servers
- **Gap Analysis** — Deterministic Python-based control checks (no LLM hallucination) against PCI-DSS v4.0 requirements
- **Policy Generation** — Natural language to OPA Rego policy conversion via Copilot agent
- **Policy Enforcement** — Evaluate Rego policies against Terraform plans with violation reporting
- **Real-time Streaming** — SSE-based progress streaming for long-running agent workflows
- **Extensible Framework** — Add new compliance frameworks by dropping a skill directory (zero code changes)
- **Copilot SDK Integration** — Full GitHub Copilot CLI SDK wiring with Pydantic-typed tools, guardrail hooks, and graceful fallback when the SDK is unavailable
- **Safety Guardrails** — Pre/post tool-use hooks that block destructive commands, enforce a shell allow-list (`opa`, `terraform`), and redact secrets from agent output

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, TypeScript, Fluent UI v9 |
| Backend | Python 3.12+, FastAPI, SSE-Starlette |
| Agent | GitHub Copilot CLI SDK (technical preview) |
| Policy Engine | Open Policy Agent (OPA), Rego |
| Infrastructure | Terraform, Azure Container Apps |
| Observability | OpenTelemetry, Azure Application Insights |
| CI/CD | GitHub Actions (3 workflows) |

## Project Structure

```
compliance-platform/
├── AGENTS.md                    # Agent persona & safety constraints
├── mcp-config/mcp.json          # MCP server configuration
├── skills/
│   ├── pci-dss/                 # PCI-DSS v4.0 skill
│   │   ├── SKILL.md
│   │   └── controls.json
│   └── policy-enforcement/      # Policy enforcement skill
│       ├── SKILL.md
│       └── rego-examples/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Settings with Key Vault overlay
│   │   ├── models/schemas.py    # Pydantic models
│   │   ├── agent/
│   │   │   ├── engine.py        # Core agent engine
│   │   │   ├── hooks.py         # OTEL metrics & hooks
│   │   │   └── skills/loader.py # Skill discovery & loading
│   │   ├── copilot/             # GitHub Copilot CLI SDK integration
│   │   │   ├── client.py        # CopilotClientManager singleton
│   │   │   ├── tools.py         # @define_tool wrappers (6 tools)
│   │   │   ├── hooks.py         # Guardrail hooks (pre/post/error)
│   │   │   └── session.py       # Session runner & streaming
│   │   ├── tools/
│   │   │   ├── evidence_assembler.py
│   │   │   ├── gap_analyzer.py
│   │   │   ├── opa_tester.py
│   │   │   └── report_generator.py
│   │   ├── mcp/
│   │   │   ├── entra_id.py      # Microsoft Graph API wrapper
│   │   │   └── purview.py       # Purview REST API wrapper
│   │   └── api/
│   │       ├── health.py
│   │       ├── evidence.py
│   │       └── policy.py
│   └── tests/
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── src/
│       ├── App.tsx
│       ├── api/client.ts
│       ├── hooks/useSSE.ts
│       ├── components/
│       └── pages/
├── infra/
│   ├── main.tf
│   ├── variables.tf
│   ├── resources.tf
│   └── outputs.tf
├── .github/workflows/
│   ├── ci.yml                   # Lint, test, validate
│   ├── deploy.yml               # Build, push, deploy
│   └── policy-gate.yml          # PR policy enforcement
├── docker-compose.yml
└── .env.example
```

## Prerequisites

- Python 3.12+
- Node.js 20+
- OPA CLI (`brew install opa` / `choco install opa`)
- Terraform 1.5+
- Docker & Docker Compose
- Azure subscription (for deployment)
- GitHub Copilot CLI SDK (`pip install github-copilot-sdk>=0.1.30`)
- GitHub Copilot CLI installed and on `PATH` (the SDK communicates with it via JSON-RPC)
- A valid GitHub token (`COPILOT_GITHUB_TOKEN`, `GH_TOKEN`, or `GITHUB_TOKEN` env var)

## Quick Start

### 1. Clone & Configure

```bash
git clone <repo-url> compliance-platform
cd compliance-platform
cp .env.example .env
# Edit .env with your Azure credentials and configuration
```

### 2. Local Development (Docker Compose)

```bash
docker-compose up --build
```

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### 3. Manual Setup

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### 4. Run Tests

```bash
# Backend tests
cd backend
pytest tests/ -v --asyncio-mode=auto

# Frontend lint
cd frontend
npm run lint
```

## Deployment to Azure

### Using Terraform

```bash
cd infra
terraform init
terraform plan -var="environment=prod" -var="project_name=compliance"
terraform apply
```

### Using CI/CD

Push to `main` branch triggers the deploy workflow:
1. Builds Docker images for backend & frontend
2. Pushes to Azure Container Registry
3. Applies Terraform to deploy Container Apps

### Policy Gate

Pull requests modifying `infra/` files automatically trigger OPA policy evaluation against the Terraform plan, with results posted as PR comments.

## Adding a New Compliance Framework

1. Create a new skill directory: `skills/<framework-name>/`
2. Add `SKILL.md` with evidence collection instructions
3. Add `controls.json` with machine-readable control definitions
4. The agent automatically discovers and loads new skills at startup

Example control definition:
```json
{
  "id": "1.1",
  "requirement": "Description of the control",
  "goal": 1,
  "evidence_sources": ["azure_nsgs", "azure_configs"],
  "pass_criteria": [
    {"check": "nsg_rules_exist", "params": {"min_count": 1}}
  ]
}
```

## Environment Variables

| Variable | Description | Required |
|----------|------------|----------|
| `AZURE_SUBSCRIPTION_ID` | Azure subscription for evidence collection | Yes |
| `AZURE_TENANT_ID` | Azure AD tenant ID | Yes |
| `AZURE_CLIENT_ID` | Service principal client ID | Yes |
| `AZURE_CLIENT_SECRET` | Service principal secret | Yes |
| `GITHUB_TOKEN` | GitHub PAT for repo access | Yes |
| `AZURE_KEYVAULT_URL` | Key Vault URL for secret management | No |
| `OTEL_EXPORTER_ENDPOINT` | OTLP endpoint for telemetry | No |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | No |

See [.env.example](.env.example) for the full list.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check with component status |
| `POST` | `/api/evidence/collect` | Start evidence collection |
| `GET` | `/api/evidence/stream/{id}` | SSE stream of collection progress |
| `GET` | `/api/evidence/report/{id}` | Get compliance report |
| `POST` | `/api/evidence/cancel/{id}` | Cancel collection |
| `POST` | `/api/policy/generate` | Generate Rego policy from description |
| `POST` | `/api/policy/enforce` | Enforce policy against Terraform |
| `GET` | `/api/policy/stream/{id}` | SSE stream of policy workflow |
| `GET` | `/api/policy/result/{id}` | Get enforcement result |
| `POST` | `/api/policy/cancel/{id}` | Cancel policy workflow |

## Copilot SDK Integration

The platform integrates the [GitHub Copilot CLI SDK](https://github.com/github/copilot-sdk/) (`github-copilot-sdk>=0.1.30`) to orchestrate compliance workflows through LLM-powered agent sessions.

### How it works

```
FastAPI Endpoint
  → AgentEngine._execute_agent()
    → copilot/session.run_copilot_session()
      → CopilotClientManager (singleton)
        → CopilotClient (JSON-RPC)
          → Copilot CLI server
            → LLM + MCP servers + custom tools
```

### Registered Tools

Six platform tools are exposed to the Copilot agent via `@define_tool` decorators with Pydantic parameter schemas:

| Tool | Description |
|------|-------------|
| `evidence_assembler_tool` | Maps raw evidence to compliance controls |
| `gap_analyzer_tool` | Deterministic pass/fail evaluation per control |
| `opa_eval_tool` | Evaluates a Rego policy against JSON input |
| `opa_test_tool` | Runs OPA unit tests for Rego policies |
| `report_generator_tool` | Generates Markdown/JSON compliance reports |
| `policy_report_tool` | Generates policy enforcement reports |

### Guardrail Hooks

Three session hooks enforce the safety constraints defined in `AGENTS.md`:

- **`on_pre_tool_use`** — Blocks destructive shell commands; only allows `opa eval`, `opa test`, `opa check`, `terraform show`, `terraform plan`
- **`on_post_tool_use`** — Scans tool output for secret patterns (API keys, tokens, connection strings) and redacts them
- **`on_error_occurred`** — Retries on timeout/rate-limit errors; aborts on fatal errors (auth failure, etc.)

### Graceful Fallback

If the Copilot CLI SDK or CLI binary is not installed, the platform starts normally and logs a warning. Agent endpoints return placeholder data instead of failing, allowing development and testing without SDK access.

## Observability

The platform exports OpenTelemetry metrics to Azure Application Insights:

- `compliance.evidence_collection.duration` — Time to collect evidence
- `compliance.gap_analysis.score` — Compliance score per run
- `compliance.policy.violations` — Violation count per enforcement
- `compliance.agent.tool_calls` — Agent tool call frequency
- `compliance.agent.sessions` — Active agent sessions
- `compliance.agent.errors` — Agent error rate
- `compliance.mcp.latency` — MCP server response times

## License

Private — All rights reserved.
