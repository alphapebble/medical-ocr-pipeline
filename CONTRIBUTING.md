# Contributing to Medical OCR Pipeline

Thank you for your interest in contributing to the Medical OCR Pipeline! This document provides guidelines for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone <your-fork-url>`
3. Set up the development environment (see `docs/development.md`)
4. Create a new branch: `git checkout -b feature/your-feature-name`

## Development Guidelines

### Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add docstrings for all functions and classes
- Keep functions small and focused

### Documentation

- Update documentation for any new features
- Include inline comments for complex logic
- Update the README if adding new capabilities
- Add examples for new functionality

### Testing

- Write unit tests for new functions
- Ensure all tests pass before submitting
- Add integration tests for new pipeline stages
- Test with various document types

### Commit Messages

Use clear, descriptive commit messages:
```
feat: add Chunkr semantic enhancement stage
fix: handle empty OCR results gracefully
docs: update configuration documentation
test: add unit tests for text cleanup functions
```

## Types of Contributions

### Bug Reports

When reporting bugs, please include:
- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- System information (OS, Python version, etc.)
- Sample files if applicable

### Feature Requests

For new features, please provide:
- Clear description of the feature
- Use case and motivation
- Proposed implementation approach
- Any breaking changes

### Code Contributions

1. **Small Changes**: Documentation fixes, small bug fixes
2. **Medium Changes**: New utility functions, performance improvements
3. **Large Changes**: New pipeline stages, major refactoring

## Development Process

### Before Starting
- Check existing issues and PRs
- Discuss large changes in an issue first
- Ensure your idea aligns with project goals

### Development
1. Write code following our style guidelines
2. Add appropriate tests
3. Update documentation
4. Test locally with various document types

### Submission
1. Push to your fork
2. Create a pull request
3. Describe your changes clearly
4. Link to related issues
5. Ensure CI tests pass

## Pull Request Guidelines

### Title and Description
- Use descriptive titles
- Explain what changes were made and why
- Reference related issues with "Fixes #123"

### Code Review Process
- All PRs require review
- Address feedback promptly
- Keep discussions constructive
- Update your PR based on feedback

### Checklist
Before submitting, ensure:
- [ ] Code follows style guidelines
- [ ] Tests are added and passing
- [ ] Documentation is updated
- [ ] No breaking changes (or clearly documented)
- [ ] Commit messages are clear

## Project Structure

Understanding the codebase:
```
medical-ocr-pipeline/
├── notebooks/          # Jupyter notebooks for pipeline stages
├── mcp/               # MCP server implementations
├── config/            # Configuration files
├── scripts/           # Utility scripts
├── docs/              # Documentation
├── tests/             # Test files
├── input_pdfs/        # Sample input files
└── outputs/           # Pipeline outputs
```

## Testing

### Running Tests
```bash
# All tests
python -m pytest tests/

# Specific test file
python -m pytest tests/test_ocr_pipeline.py

# With coverage
python -m pytest --cov=src tests/
```

### Writing Tests
- Place tests in the `tests/` directory
- Use descriptive test names
- Test both success and failure cases
- Mock external dependencies when appropriate

## Documentation

### Building Documentation
```bash
# Install documentation dependencies
pip install -r docs/requirements.txt

# Build documentation
mkdocs build

# Serve locally
mkdocs serve
```

### Writing Documentation
- Use clear, concise language
- Include code examples
- Keep documentation up to date
- Consider different user skill levels

## Community Guidelines

### Be Respectful
- Use inclusive language
- Be patient with newcomers
- Provide constructive feedback
- Help others learn

### Communication
- Use GitHub issues for bug reports and feature requests
- Join discussions in pull requests
- Ask questions if something is unclear

## Release Process

Releases follow semantic versioning (MAJOR.MINOR.PATCH):
- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

## Getting Help

If you need help:
1. Check the documentation
2. Search existing issues
3. Create a new issue with the "question" label
4. Be specific about what you're trying to achieve

## Recognition

Contributors will be:
- Listed in the project README
- Credited in release notes
- Invited to join the maintainer team (for significant contributions)

Thank you for contributing to making medical document processing more accessible and accurate!