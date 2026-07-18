# Contributing to Memship

Thank you for your interest in contributing to Memship!

## Current Status

Memship is in active development. The foundation — infrastructure, CI/CD, and core architecture — is in place, and **code contributions are welcome**. See the [roadmap](README.md#roadmap) for what is shipped and what is planned.

## How You Can Help

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

## Code Contributions

### Branching model — GitHub Flow

Memship uses **GitHub Flow**: `main` is the trunk and always deployable.

- `main` is the single long-lived branch. It is what the staging environment deploys and what releases are cut from.
- All work happens on **short-lived `feature/*` branches** taken from `main` and merged back through a pull request. There is no `develop` or `integration` branch.
- Every push to `main` builds **release-candidate images** that staging validates before any release.

### Getting Started

1. Fork the repository (or, if you have push access, clone it directly)
2. Create a `feature/*` branch from `main`
3. Make your changes
4. Run the tests to ensure nothing is broken
5. Open a pull request against `main`

### Development Setup

**Prerequisites:** Docker + Docker Compose, Node.js 22+ with [pnpm](https://pnpm.io), and [uv](https://github.com/astral-sh/uv) for Python.

The backend (API, PostgreSQL, Redis, Celery worker and beat) runs in Docker; the frontend runs locally with pnpm. One script manages all of it:

```bash
./scripts/dev.sh start all     # Start backend (Docker) + frontend (local)
./scripts/dev.sh status        # Show what is running
./scripts/dev.sh stop all      # Stop everything
```

Then seed the database with test accounts:

```bash
./scripts/dev.sh seed test     # Creates test accounts and sample data, no prompts
```

The app is at http://localhost:3000 and the API docs at http://localhost:8003/api/docs. Log in with `admin@test.com` / `TestAdmin1!`.

Run the backend tests with `./scripts/dev.sh test`.

See the [Development section of the README](README.md#development) for the full command reference, service URLs, and the rest of the seeded test accounts.

> **Note:** Python dependencies are baked into the backend Docker image — `pyproject.toml` is not bind-mounted. After adding or upgrading a backend dependency, rebuild the image or the running container will not have it:
>
> ```bash
> docker compose -f backend/docker/docker-compose.yml build --no-cache api
> docker compose -f backend/docker/docker-compose.yml up -d --force-recreate api
> ```

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

## Releases

Releases are driven by **git tags — there is no `VERSION` file and no version-bumping git hooks.** The git tag is the single source of truth for the version.

The flow is **build once, promote**:

1. A PR merges to `main`. CI runs, then the Build Images workflow pushes **release-candidate images** tagged `sha-<commit>` and `main` to GHCR.
2. The staging environment deploys that RC image and it is validated there.
3. To release the validated commit, a maintainer tags it and pushes the tag:

   ```bash
   ./scripts/release.sh 1.3.0          # tags HEAD (must be a validated commit on main)
   ./scripts/release.sh 1.3.0 <sha>    # or tag a specific validated commit
   ```

   This creates an annotated `v1.3.0` tag and pushes it.
4. The Release workflow **promotes the exact RC image** for that commit to `:1.3.0` and `:latest` — it does not rebuild, so staging and production ship identical bytes. It also checks that the version has a row in the README roadmap.

The version the running app reports comes from the `APP_VERSION` environment variable (set from the image tag at deploy time); running from source, it falls back to `git describe`.

## License

By contributing to Memship, you agree that your contributions will be licensed under the [Elastic License 2.0 (ELv2)](LICENSE).
