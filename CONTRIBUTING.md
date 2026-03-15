# Contributing to Healthcare AI Live2D

Thank you for your interest in contributing to the Healthcare AI Live2D project! This document provides guidelines for contributing.

## Code of Conduct

Please be respectful and constructive in all interactions. This is a healthcare-focused project, and we take user safety seriously.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/healthcare-ai-live2d.git`
3. Create a feature branch: `git checkout -b feature/your-feature-name`
4. Set up the development environment (see below)

## Development Setup

```bash
cd healthcare_ai_live2d_unified

# Copy environment template
cp env.example .env

# Edit .env with your AWS credentials
# Get AWS credentials from AWS IAM console

# Start services with Docker
docker-compose up -d

# Or for local development
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Code Style

- **Python**: Follow PEP 8, use Black for formatting
- **JavaScript**: Use consistent indentation (2 spaces)
- **HTML/CSS**: Follow existing patterns in the codebase

### Running Linters

```bash
# Format Python code
black src/ tests/

# Lint Python code
ruff check src/ --fix

# Type checking
mypy src/
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_specific.py -v

# Run with coverage
pytest --cov=src tests/
```

## Pull Request Process

1. Ensure all tests pass
2. Update documentation if needed
3. Add tests for new functionality
4. Follow the commit message format below
5. Submit a pull request with a clear description

### Commit Message Format

```
type(scope): description

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Example:
```
feat(agents): add new wellness coaching skill

- Added sleep support skill
- Updated skill router
- Added tests for new skill
```

## Security Considerations

This is a healthcare application. Please:

- **NEVER** log or expose patient data
- **ALWAYS** use parameterized queries
- **ALWAYS** validate user input
- **NEVER** commit API keys or secrets
- Follow the privacy guidelines in `.kiro/steering/009_privacy_compliance.md`

## Questions?

Open an issue for questions or discussions about contributing.

Thank you for helping improve Healthcare AI! 🏥💙
