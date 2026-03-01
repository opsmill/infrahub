# Quickstart: Configuration Wizard with Marketplace Schema Browser

**Feature**: atg-01-config-wizard | **Date**: 2026-02-26

## What This Feature Does

When a fresh Infrahub instance has no user-defined schemas, a configuration wizard appears to guide users through:
1. Creating Git credentials
2. Connecting a Git repository
3. Browsing and selecting schemas from the Infrahub Marketplace
4. Installing selected schemas via a background job

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                         │
│                                                             │
│  SchemaProvider ──► detects no user schemas ──► shows Wizard│
│                                                             │
│  Wizard Steps:                                              │
│  [Welcome] → [Credentials] → [Repository] → [Schemas] → [Install]
│       │            │              │             │            │
│       │        GraphQL         GraphQL      REST API     REST API
│       │        mutation        mutation     (proxy)      (trigger)
│                                                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   BACKEND   │
                    │  (FastAPI)  │
                    ├─────────────┤
                    │ /api/marketplace/* │ ◄── New REST endpoints
                    │    │               │
                    │    ▼               │
                    │ HttpxAdapter ──────┼──► marketplace.infrahub.app/graphql
                    │                   │
                    │ /api/marketplace/  │
                    │   install (POST)   │
                    │    │               │
                    │    ▼               │
                    │ Prefect Workflow   │
                    │    │               │
                    │    ▼               │
                    │ Git: write files,  │
                    │ commit, push       │
                    └───────────────────┘
```

## Key Files to Create/Modify

### Backend (New Files)

| File | Purpose |
|------|---------|
| `backend/infrahub/api/marketplace.py` | REST endpoints proxying marketplace API |
| `backend/infrahub/marketplace/models.py` | Pydantic models for marketplace responses |
| `backend/infrahub/marketplace/client.py` | Marketplace GraphQL client using HttpxAdapter |
| `backend/infrahub/marketplace/tasks.py` | Prefect workflow for schema installation |

### Backend (Modified Files)

| File | Purpose |
|------|---------|
| `backend/infrahub/api/main.py` | Register marketplace router |
| `backend/infrahub/workflows/catalogue.py` | Register `MARKETPLACE_SCHEMA_INSTALL` workflow |

### Frontend (New Files)

| File | Purpose |
|------|---------|
| `frontend/app/src/entities/marketplace/` | New entity directory |
| `frontend/app/src/entities/marketplace/api/marketplace.queries.ts` | API calls to marketplace proxy |
| `frontend/app/src/entities/marketplace/ui/marketplace-schema-card.tsx` | Schema card component |
| `frontend/app/src/entities/marketplace/ui/marketplace-browser.tsx` | Schema grid with search/filter |
| `frontend/app/src/entities/marketplace/types.ts` | TypeScript types |
| `frontend/app/src/entities/config-wizard/` | New entity directory |
| `frontend/app/src/entities/config-wizard/ui/config-wizard.tsx` | Main wizard component |
| `frontend/app/src/entities/config-wizard/ui/wizard-step-credentials.tsx` | Step: Create credentials |
| `frontend/app/src/entities/config-wizard/ui/wizard-step-repository.tsx` | Step: Configure repository |
| `frontend/app/src/entities/config-wizard/ui/wizard-step-schemas.tsx` | Step: Browse/select schemas |
| `frontend/app/src/entities/config-wizard/ui/wizard-step-confirm.tsx` | Step: Confirm and install |

### Frontend (Modified Files)

| File | Purpose |
|------|---------|
| `frontend/app/src/pages/app-layout.tsx` | Add wizard trigger based on schema detection |

## Development Sequence

1. **Backend marketplace proxy** → Can be tested independently with curl/httpie
2. **Backend install workflow** → Can be tested with direct API calls
3. **Frontend marketplace entity** → Schema cards and browser, testable in isolation
4. **Frontend wizard entity** → Multi-step wizard flow using existing form patterns
5. **Integration** → Wire wizard into app-layout with schema detection trigger
6. **E2E tests** → Full flow from wizard trigger to schema installation

## Testing Strategy

- **Backend unit tests**: Marketplace client, Pydantic model validation, proxy endpoint responses
- **Backend integration tests**: Workflow execution with mock marketplace responses
- **Frontend unit tests**: Schema card rendering, wizard step navigation, schema detection hook
- **Frontend E2E tests**: Full wizard flow with mocked marketplace API
