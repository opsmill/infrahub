# Copilot Instructions for Infrahub

These guidelines help AI coding agents work productively in the Infrahub repo. Follow these project-specific conventions and workflows for best results.

## Overview of Infrahub

Infrahub from OpsMill is taking a new approach to Infrastructure Management by providing a new generation of datastore to organize and control all the data that defines how an infrastructure should run. Infrahub offers a central hub to manage the data, templates and playbooks that powers your infrastructure by combining the version control and branch management capabilities similar to Git with the flexible data model and UI of a graph database.

Documentation generated for Infrahub must reflect this novel approach, providing clarity around new concepts and demonstrating how they integrate with familiar patterns from existing tools like Git, infrastructure-as-code, and CI/CD pipelines.

## Architecture Overview

- **Monorepo**: Contains backend (Python), frontend (React), docs, and infrastructure tools.
- **Backend**: Located in `backend/infrahub/`, implements the core graph-based infrastructure datastore, API, and business logic.
- **Frontend**: Under `frontend/app/` and `frontend/packages/`, built with React (Create React App) and custom UI packages.
- **Docs**: In `docs/`, built with Docusaurus. Use `npm start` for local dev, `npm run build` to generate static site.

## Developer Workflows

- **Backend**: Use uv for dependency management (`pyproject.toml`). Run tests with `pytest` or via `invoke` tasks.
- **Frontend**: Use npm scripts (`npm start`, `npm test`, `npm run build`) in `frontend/app/`.
- **Docs**: Develop in `docs/`, preview with `invoke docs.build docs.serve`. Validate docs site with `invoke docs.validate`.

## Project Conventions

- **Testing**: Place backend tests in `backend/tests/`, SDK tests in `python_sdk/tests/`, and frontend tests alongside components.
- **Docs**: Write guides in `docs/docs/guides/`, reference in `docs/docs/reference/`. Use Docusaurus markdown/MDX features.
- **Community/Contributing**: See `CONTRIBUTING.md` and `SECURITY.md` at repo root for policies.

## Integration Points

- **API**: Backend exposes API for UI and SDKs.
