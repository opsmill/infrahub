# Infrahub Documentation Style Guide

This guide defines capitalization and grammar rules for Infrahub documentation.

## Core Principle

> **Capitalize nouns that represent first-class, named Infrahub capabilities with defined behavior and APIs.**
> **Do not capitalize generic industry concepts, even when Infrahub produces or uses them.**

## Capitalization Rules

### Generators

**Always capitalize** when referring to the Infrahub feature.

Generator is not a widely established industry term. In Infrahub, a Generator is a named system concept with specific semantics (idempotent, service-model-driven, graph-aware).

| Usage | Correct | Incorrect |
|-------|---------|-----------|
| Feature reference | "Infrahub **Generators** convert service models into objects." | "Infrahub generators convert..." |
| Plural | "Configure your **Generators** in the repository." | "Configure your generators..." |

### Transformations

**Always capitalize** when referring to the Infrahub feature. Use "transform" only as a verb, never as a noun.

While "transformation" is a common word, Infrahub Transformations have a specific execution model, defined inputs (GraphQL queries), and defined outputs (artifacts).

| Usage | Correct | Incorrect |
|-------|---------|-----------|
| Feature reference | "**Transformations** convert graph data into artifacts." | "transformations convert..." |
| As a verb | "Use this to **transform** data into vendor formats." | "Use this Transform to..." |
| Noun form | "Create a **Transformation** for config generation." | "Create a transform for..." |

**Never use "transform" or "transforms" as a noun.** Always use "Transformation" or "Transformations".

### Artifacts

**Do NOT capitalize** unless it starts a sentence or is at the beginning of a bullet point where other items are also capitalized.

Artifact is a broadly accepted industry term. Infrahub artifacts are not conceptually novel in the same way Generators or Transformations are.

| Usage | Correct | Incorrect |
|-------|---------|-----------|
| Mid-sentence | "The **artifact** is stored in object storage." | "The Artifact is stored..." |
| Start of sentence | "**Artifacts** are generated automatically." | "artifacts are generated..." |
| In a capitalized list | "- **Artifacts**: Generated outputs..." | "- **artifacts**: Generated outputs..." (if other items start capitalized) |

### Profiles

**Always capitalize** when referring to the Infrahub feature.

| Usage | Correct | Incorrect |
|-------|---------|-----------|
| Feature reference | "Infrahub **Profiles** allow you to..." | "Infrahub profiles allow..." |
| Plural | "Create **Profiles** for your devices." | "Create profiles for..." |

### Resource Manager

**Always capitalize** and **always use singular form**.

| Usage | Correct | Incorrect |
|-------|---------|-----------|
| Feature reference | "Use **Resource Manager** to allocate IPs." | "Use Resource Managers..." |
| Plural context | "Configure **Resource Manager** instances." | "Configure Resource Managers." |

## Bullet Point Lists

When a word appears at the start of a bullet point in a list where other items begin with capitalized words, capitalize it for consistency.

**Correct:**
```markdown
- **Caching**: Generated artifacts are stored...
- **Traceability**: Past values remain available...
- **Peer Review**: Artifacts are automatically part of...
- **Database**: Artifact nodes are stored...
```

**Incorrect:**
```markdown
- **Caching**: Generated artifacts are stored...
- **Traceability**: Past values remain available...
- **Peer Review**: artifacts are automatically part of...  <!-- Should be capitalized -->
- **Database**: artifact nodes are stored...               <!-- Should be capitalized -->
```

## Link Text in Lists

When a word appears as link text at the start of a bullet point in a list where other items begin with capitalized words, capitalize it.

**Correct:**
```markdown
- [Version control](version-control): Understand how branches work...
- [Schema](schema): Learn about data models...
- [Artifacts](artifact): Explore generated outputs...
- [Generators](generator): Learn about code generation...
```

**Incorrect:**
```markdown
- [Version control](version-control): Understand how branches work...
- [Schema](schema): Learn about data models...
- [artifacts](artifact): Explore generated outputs...  <!-- Should be capitalized -->
- [generators](generator): Learn about code generation...  <!-- Should be capitalized -->
```

## Quick Reference Table

| Term | Capitalize? | Notes |
|------|-------------|-------|
| Generator(s) | Yes | Infrahub-specific primitive |
| Transformation(s) | Yes | First-class capability (noun form) |
| transform | No | Verb only |
| artifact(s) | No | Generic industry term (capitalize at sentence/list start) |
| Profile(s) | Yes | Infrahub-specific feature |
| Resource Manager | Yes | Always singular, system-level capability |

## Product and Technology Names

Always use correct capitalization for these terms:

- Ansible
- Docker, DockerHub
- GitHub, GitLab, GitPod
- Grafana
- GraphQL
- InfluxDB
- Infrahub
- Jinja2
- K3s, K8s, Kubernetes
- MySQL
- Neo4j
- NGINX
- Node.js
- OpenAPI, OpenConfig
- OpsMill
- PostgreSQL
- Prometheus
- Python
- RabbitMQ
- Terraform
- Ubuntu
- VS Code
