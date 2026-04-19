# Contributing to Cellular Council Architecture

Thank you for your interest in contributing to CCA! This document provides guidelines
and information for contributors.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/HakanKeskinoglu/cellular-council.git
   cd cellular-council
   ```
3. Install in development mode:
   ```bash
   pip install -e ".[all]"
   pre-commit install
   ```
4. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

### Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=cca --cov-report=term-missing

# Specific test file
pytest tests/unit/test_core.py -v
```

### Code Quality

We use `ruff` for linting and `mypy` for type checking:

```bash
ruff check cca/
mypy cca/ --ignore-missing-imports
```

### Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation changes
- `test:` — Adding or updating tests
- `refactor:` — Code refactoring without behavior change
- `chore:` — Maintenance tasks

Examples:
```
feat: add SecurityCell with threat analysis capabilities
fix: correct consensus weight normalization in Delphi strategy
docs: add AlertMind integration example
test: add integration tests for multi-round debate
```

## Architecture Overview

Before contributing, understand the core concepts:

- **Cells** — Specialized AI agents (Risk, Ethics, Technical, Financial, Security)
- **Cluster** — Groups of cells that engage in structured debate
- **Consensus Engine** — Aggregates cell outputs using configurable strategies
- **Council** — Top-level orchestrator that manages the full deliberation pipeline
- **LLM Backends** — Pluggable providers (Ollama, OpenAI, Anthropic)

## How to Contribute

### Adding a New Cell Type

1. Create a new class in `cca/cells/` that extends `BaseCell`
2. Define a role-specific system prompt
3. Register the cell role in `CellRole` enum
4. Add unit tests in `tests/unit/`
5. Update `__init__.py` exports

### Adding a New Consensus Strategy

1. Add the strategy to `ConsensusStrategy` enum
2. Implement the strategy method in `ConsensusEngine`
3. Add tests covering edge cases
4. Document the strategy's use case in docstrings

### Adding a New LLM Backend

1. Create a new class in `cca/llm/` that extends `BaseLLMBackend`
2. Implement `generate()` and `health_check()` methods
3. Add to the backend registry
4. Include connection/auth handling

## Pull Request Process

1. Ensure all tests pass: `pytest tests/ -v`
2. Ensure code quality: `ruff check cca/ && mypy cca/`
3. Update documentation if needed
4. Write a clear PR description explaining the change
5. Reference any related issues

## Reporting Issues

Use GitHub Issues with the provided templates:
- **Bug Report** — For bugs and unexpected behavior
- **Feature Request** — For new features or improvements

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
