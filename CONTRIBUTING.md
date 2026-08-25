# Contributing to Delibra

Thank you for helping improve inspectable multi-model reasoning.

## Development workflow

1. Fork the repository and create a focused branch.
2. Create a Python 3.11+ virtual environment.
3. Install `requirements-dev.txt`.
4. Keep provider behavior behind `ProviderRegistry`; tests must use fakes and never spend API credits.
5. Add or update tests for every behavior change.
6. Run the complete quality gate before opening a pull request:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest --cov=verdictforge --cov-report=term-missing
node --check verdictforge/web/app.js
```

## Pull requests

Keep changes reviewable and explain user-visible behavior, failure modes, and configuration changes. Do not commit provider keys, `.env`, databases, generated coverage, or live API responses.

## Design principles

- Prefer explicit validated contracts over loosely shaped dictionaries.
- Preserve candidate anonymity through the judging boundary.
- Let one provider fail without destroying unrelated successful work.
- Keep rating calculations pure, deterministic, and order-independent.
- Expose honest operational limits in documentation.
