# Contributing to Nubo Native Platform (NNP)

This repository, **ai-rag-query-service**, is part of the Nubo Native Platform
(NNP) Knowledge Management and RAG service layer. Contributions should improve
the reliability, security, maintainability, and operational clarity of the
service.

## Before You Start

Contributions should align with an open **Issue**, the published **Roadmap**, or
a proposed **enhancement**. Email **contribution@nubons.com** with your approach
and category first; we respond within 5 working days.

Before making changes, review:

- [README.md](README.md) for project setup and runtime behavior.
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for participation standards.
- [DEVELOPMENT_GUIDELINES.md](DEVELOPMENT_GUIDELINES.md) once added for coding
  conventions and service-specific engineering standards.

## Development & Contribution Steps

1. **Fork & Clone**: Fork the repository and create a feature branch from the
   active development branch.
2. **Set Up Locally**: Create a Python virtual environment and install
   dependencies with `pip install -r requirements.txt`.
3. **Configure Safely**: Copy `.env.sample` to `.env` for local development.
   Use placeholders or local-only values. Never commit `.env` or secrets.
4. **Make Focused Changes**: Keep changes scoped to the issue or enhancement.
   Avoid unrelated formatting, dependency churn, or broad refactors.
5. **Verify Locally**: Start the service with Uvicorn and confirm the health
   endpoint responds. If you add tests, run the relevant test command before
   submitting.
6. **Container Check**: For changes that affect dependencies, startup, or
   deployment behavior, build the Docker image locally.
7. **Submit PR**: Open a Pull Request with a descriptive summary, verification
   notes, configuration impact, and any known limitations.

## Local Verification

Minimum local checks before opening a Pull Request:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl http://localhost:8000/
```

For Docker-impacting changes:

```bash
docker build -t ai-rag-query-service .
```

If your change adds tests or introduces a test framework, include the exact test
command in the Pull Request description.

## Pull Request Expectations

Pull Requests should include:

- A clear summary of what changed and why.
- Linked issue, roadmap item, or enhancement context where applicable.
- Local verification steps performed.
- Configuration keys added, removed, or changed.
- API request or response contract changes, if any.
- Security considerations for model keys, MinIO credentials, config server
  values, and request-level `APIKey` handling.

## Security & Standards

- **Never commit secrets, tokens, internal hostnames, private keys, or `.env`
  files.** Use placeholders in documentation and environment samples.
- Keep request-level `APIKey` values out of logs.
- Do not hardcode environment-specific hosts, ports, credentials, bucket names,
  model names, or collection names unless they are safe defaults intended for
  all environments.
- Validate changes involving Milvus, MinIO, OpenAI-compatible APIs, Ollama, and
  config server behavior carefully.
- All participation is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).
