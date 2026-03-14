# Contributing to Memship

Thank you for your interest in contributing to Memship!

## Current Status

Memship is in early development. The project foundation (infrastructure, CI/CD, core architecture) is being built. Once the foundation is stable, we will actively welcome code contributions.

## How You Can Help Now

### Feature Requests & Ideas

Open an [issue](https://github.com/marcandreuf/memship/issues) to suggest features, improvements, or share how you'd use Memship. Label your issue with `feature-request` or `idea`.

### Bug Reports

If you find a bug, open an [issue](https://github.com/marcandreuf/memship/issues) with:
- A clear description of the problem
- Steps to reproduce it
- Expected vs actual behavior
- Your environment (OS, Docker version, browser)

### Questions & Discussion

Have a question or want to discuss the project direction? Open an [issue](https://github.com/marcandreuf/memship/issues) with the `question` label.

## Code Contributions (Coming Soon)

Once the project is ready for code contributions, the following guidelines will apply:

### Getting Started

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Run tests to ensure nothing is broken
5. Submit a pull request

### Development Setup

Detailed setup instructions will be added once the infrastructure is in place.

### Commit Messages

- Use clear, descriptive commit messages
- Start with a verb in imperative mood (e.g., "Add member search endpoint")
- Keep the first line under 72 characters

### Pull Requests

- Keep PRs focused — one feature or fix per PR
- Include a clear description of what the PR does and why
- Reference related issues (e.g., "Closes #42")
- Ensure all tests pass

### Code Style

- **Python (backend):** Follow project linting rules (ruff)
- **TypeScript (frontend):** Follow project ESLint configuration
- All user-facing text must use translation keys (i18n) — never hardcode strings

## License

By contributing to Memship, you agree that your contributions will be licensed under the [Elastic License 2.0 (ELv2)](LICENSE).
