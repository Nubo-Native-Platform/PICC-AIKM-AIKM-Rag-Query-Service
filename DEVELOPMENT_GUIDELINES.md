# Development Guidelines and Contribution Standards: `ai-rag-query-service`

This document defines the architectural standards, development workflows,
coding conventions, and security requirements for contributors to
**`ai-rag-query-service`**.

---

## Table of Contents

1. [Architecture & Design Principles](#1-architecture--design-principles)
2. [Development Environment Setup](#2-development-environment-setup)
3. [Package Structure & Code Navigation](#3-package-structure--code-navigation)
4. [Coding Standards & Best Practices](#4-coding-standards--best-practices)
   - [FastAPI Route Boundaries](#fastapi-route-boundaries)
   - [Pydantic Request and Response Models](#pydantic-request-and-response-models)
   - [Config Server and Local Overrides](#config-server-and-local-overrides)
   - [Milvus Search and Collection Handling](#milvus-search-and-collection-handling)
   - [Summarizer and Model Provider Handling](#summarizer-and-model-provider-handling)
   - [Image Asset Metadata Handling](#image-asset-metadata-handling)
   - [Logging & Sensitive Data Masking](#logging--sensitive-data-masking)
5. [Security, Code Quality & Compliance Tooling](#5-security-code-quality--compliance-tooling)
   - [Secret and Configuration Hygiene](#secret-and-configuration-hygiene)
   - [Dependency Review](#dependency-review)
   - [Container Review](#container-review)
6. [Git Workflow & Branching Strategy](#6-git-workflow--branching-strategy)
   - [Branch Naming Conventions](#branch-naming-conventions)
   - [Conventional Commits](#conventional-commits)
7. [Pull Request (PR) Checklist](#7-pull-request-pr-checklist)
8. [Release Lifecycle & Versioning](#8-release-lifecycle--versioning)

---

## 1. Architecture & Design Principles

`ai-rag-query-service` serves as the retrieval and answer-generation layer for
NNP Knowledge Management RAG workflows. All modifications must comply with
these core tenets:

1. **Zero-Trust Hardcoded Configuration**: Never commit private IP addresses,
   internal domains, production credentials, bucket names, static API keys, or
   environment-specific model and collection names. Use config server values,
   `.env.sample` placeholders, and documented environment variables.
2. **Clear Route-Service Separation**: FastAPI route handlers should validate
   requests and coordinate workflow only. Search, summarization, image metadata,
   config loading, and external integrations belong in `src/core` or
   `src/services`.
3. **Deterministic Startup Configuration**: Required runtime settings are
   validated during startup. When adding new settings, include them in the
   settings model, validation list, `.env.sample`, README, and deployment
   documentation.
4. **Provider-Safe Model Selection**: Public and local model paths must remain
   explicit. Avoid silently mixing public embeddings with local vector
   collections or local embeddings with public vector collections.
5. **Text-Only Generated Answers**: The summarizer must not emit markdown image
   syntax, invented URLs, or placeholder links. Image assets must be returned in
   the `images` response array.
6. **Sensitive Data Minimization**: Do not log API keys, authorization headers,
   MinIO credentials, `.env` contents, full config payloads, or request-level
   `APIKey` values.

---

## 2. Development Environment Setup

### Required Tools

- **Python 3.13+**.
- **pip** for installing dependencies from `requirements.txt`.
- **Docker** for container build verification.
- **Milvus** access for vector search validation.
- **MinIO** access when validating image asset metadata behavior.
- **Ollama** when validating `modelType=local` summarization.
- **OpenAI-compatible API key** when validating public embeddings or public
  summarization.
- **IDE**: VS Code, PyCharm, or another Python-aware editor with type hints and
  Markdown support.

### Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.sample .env
```

Populate `.env` with local-only values or placeholders. Do not commit `.env`.

---

## 3. Package Structure & Code Navigation

```text
.
|-- main.py                         # FastAPI app, request/response models, routes
|-- src/
|   |-- core/
|   |   |-- config.py               # Effective settings and required config validation
|   |   |-- config_server.py        # Config server bootstrap and local overrides
|   |   `-- milvus_vectorstore.py   # Embedding selection and Milvus search logic
|   `-- services/
|       |-- minio_storage.py        # Image asset metadata enrichment
|       |-- rag_response_builder.py # Source and image response shaping
|       `-- rag_summarizer.py       # Public/local LLM summarization
|-- Dockerfile                      # Container runtime definition
|-- requirements.txt                # pip dependency list
|-- pyproject.toml                  # Python project metadata and dependency constraints
|-- uv.lock                         # Locked dependency state where applicable
`-- .env.sample                     # Safe local configuration template
```

---

## 4. Coding Standards & Best Practices

### FastAPI Route Boundaries

- Keep route handlers in `main.py` small and readable.
- Use routes for request validation, orchestration, and response assembly.
- Move reusable behavior into `src/core` or `src/services`.
- Do not add external service calls directly into route handlers when they can
  be isolated behind a service helper.

### Pydantic Request and Response Models

- Keep request and response contracts explicit with Pydantic models.
- Add defaults only when the default is safe for all environments.
- Preserve backward compatibility for existing fields such as `collectionNames`,
  `sourceCount`, `similarityThreshold`, `extendPublicInfo`, `modelType`,
  `ModelName`, and `APIKey`.
- Document request or response contract changes in the README and PR summary.

### Config Server and Local Overrides

- Add new runtime settings to `Settings` in `src/core/config.py`.
- Add required settings to `REQUIRED_CONFIG_KEYS` only when startup should fail
  without them.
- Add sensitive keys to `SECRET_CONFIG_KEYS`.
- Add safe examples to `.env.sample`; use placeholders, not real values.
- Keep bootstrap keys separate from runtime overrides.
- Do not print raw config server payloads or secret-bearing environment values.

### Milvus Search and Collection Handling

- Resolve collection names through a single helper path.
- Validate requested collections against existing Milvus collections before
  searching.
- Preserve public/local collection separation:
  - `MILVUS_COLLECTION_NAME` for public embeddings.
  - `MILVUS_COLLECTION_NAME_LOCAL` for local embeddings.
- Check embedding dimensions before searching a collection.
- Apply `sourceCount` and `similarityThreshold` consistently across requested
  collections.
- Return source metadata required by the KM backend whenever it is available.

### Summarizer and Model Provider Handling

- Keep public and local summarization paths explicit.
- Use request-level `ModelName` and `APIKey` overrides only for the current
  request.
- Do not persist request-level API keys.
- Keep prompt templates configurable through the config server.
- Preserve the instruction that generated answers must be text only and must
  not include image URLs or markdown image syntax.
- Handle provider errors by returning an empty summary or a documented fallback
  response without exposing credentials or raw provider payloads.

### Image Asset Metadata Handling

- Return image metadata in the `images` array, not inside generated answer text.
- Require `object_key` for usable image assets.
- Use the configured MinIO bucket when chunk metadata does not include a bucket.
- Do not expose browser-facing signed URLs from this service.
- Keep KM backend image streaming assumptions documented when changing metadata
  shape.

### Logging & Sensitive Data Masking

- Prefer structured, concise log messages over raw `print` output for new code.
- Never log API keys, tokens, authorization headers, MinIO passwords, `.env`
  values, or full request payloads containing `APIKey`.
- Log enough operational context to diagnose collection resolution, provider
  path, and result counts without exposing sensitive data.
- Reduce noisy third-party logs when they make service logs difficult to use.

---

## 5. Security, Code Quality & Compliance Tooling

This repository does not currently define a dedicated local lint or test command.
Do not document mandatory tooling until it is configured in the repository.

### Secret and Configuration Hygiene

- Keep `.env` ignored and out of version control.
- Use placeholders in documentation and `.env.sample`.
- Review diffs for internal hostnames, IP addresses, tokens, and credentials
  before opening a PR.

### Dependency Review

- Review changes to `requirements.txt`, `pyproject.toml`, and `uv.lock`.
- Prefer pinned or constrained dependencies where the project already provides
  them.
- Avoid adding heavyweight libraries for small helper behavior.
- Validate dependency changes with a clean virtual environment install.

### Container Review

For Docker-impacting changes, run:

```bash
docker build -t ai-rag-query-service .
```

Review the Dockerfile for unnecessary packages, build-time secrets, and
environment-specific values.

---

## 6. Git Workflow & Branching Strategy

### Branch Naming Conventions

- `feature/<issue-number>-short-description`
- `fix/<issue-number>-bug-title`
- `docs/<short-description>`
- `refactor/<short-description>`

### Conventional Commits

Use standard commit messages:

```text
feat(rag): add collection-level search filtering
fix(config): validate missing local model name during startup
docs(readme): align quick start with config server bootstrap
refactor(search): isolate Milvus collection resolution
```

---

## 7. Pull Request (PR) Checklist

Before submitting a Pull Request, ensure:

- [ ] The service installs cleanly with `pip install -r requirements.txt`.
- [ ] The service starts locally with `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`.
- [ ] The health endpoint responds successfully in your local environment.
- [ ] Docker builds successfully when dependencies, startup behavior, or the
      Dockerfile changed.
- [ ] Any added test framework or tests include the exact command in the PR
      description.
- [ ] No hardcoded credentials, internal hostnames, private IPs, tokens, or
      `.env` files are committed.
- [ ] README and deployment/user documentation are updated for config, API, or
      operational behavior changes.
- [ ] Request and response model changes are backward compatible or clearly
      documented as breaking changes.
- [ ] Logs do not expose request-level `APIKey`, OpenAI keys, MinIO passwords,
      or config server secret values.

---

## 8. Release Lifecycle & Versioning

- Keep application versioning aligned with release tags and CI/CD image tags.
- Treat API contract changes as release-relevant changes.
- Document new required configuration before deployment.
- Verify config server values exist for the target environment before rollout.
- For production releases, confirm container image build, image scan, and
  deployment pipeline status in CI/CD.
