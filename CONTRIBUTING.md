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
- All work happens on **short-lived `feature/*` branches** taken from `main` and merged back through a pull request.
- Every push to `main` builds **release-candidate images** that staging validates before any release.

**There are no long-lived environment branches** — no `develop`, `integration`, `preproduction`, `release/*`, or `hotfix/*`. GitHub Flow deliberately rejects the multi-branch Git Flow model: at this team size its ceremony is overhead, and in Git Flow `develop` *is* the integration branch, so a separate `develop` **and** `integration` (or `preproduction`) branch is redundant. One trunk avoids the question entirely.

#### Branches vs. environments

The most common point of confusion: **"preproduction" (staging) is an *environment*, not a branch.** Environments are targets you deploy an image *to*; they do not each need a matching branch. The mapping is:

| Environment | What deploys there | Trigger |
|---|---|---|
| **Staging** (preproduction) | the release-candidate image built from `main` (`sha-<commit>` / `main`) | every merge to `main` |
| **Production** | the *same* RC image, re-tagged `:X.Y.Z` + `:latest` (build once, promote — never rebuilt) | pushing a `v*.*.*` git tag |

So there is nothing to "prepare" as a `preproduction` branch — a pre-production gate is provided by the **staging environment** deploying the RC image and validating it before any tag is cut. See [Releases](#releases) below for the promote flow.

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

The app is at http://localhost:3000 and the API docs at http://localhost:8003/api/docs. Log in with `admin@examplee6e3b1.com` / `TestAdmin1!`.

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

### Choosing a version

Version numbers follow [semantic versioning](https://semver.org/) and are **chosen at release time, not reserved on the roadmap in advance.** The [roadmap](README.md#roadmap) lists planned features without numbers; a feature only gets its number when it ships. Pick it relative to the latest released tag:

- **Minor** (`x.Y.0`) — a new feature or roadmap item (a new domain, a new member-facing capability).
- **Patch** (`x.y.Z`) — bug fixes and small polish, no new feature.
- **Major** (`X.0.0`) — a breaking change to the API, data model, or deployment/upgrade contract.

Because features are built in parallel, **the number is claimed at release, not when you branch.** Whoever releases first takes the next number; the next feature to ship takes the one after — so don't hard-code a target version into your branch, commits, or the roadmap while the work is in flight. When your feature is ready, add its row to the **Released** table in the [roadmap](README.md#roadmap) *in the same PR as the feature code*, then tag. That is also what satisfies the roadmap guard (step 4 below): the tagged commit must already carry the released version's README row.

The flow is **build once, promote**:

1. A PR merges to `main`. CI runs, then the Build Images workflow pushes **release-candidate images** tagged `sha-<commit>` and `main` to GHCR. **Every service is built on every commit**, even one it did not touch, so each commit on `main` has a complete RC set and any of them can be released.
2. The staging environment deploys that RC image and it is validated there.
3. To release the validated commit, a maintainer tags it and pushes the tag:

   ```bash
   ./scripts/release.sh 1.3.0          # tags HEAD (must be a validated commit on main)
   ./scripts/release.sh 1.3.0 <sha>    # or tag a specific validated commit
   ```

   This creates an annotated `v1.3.0` tag and pushes it.
4. The Release workflow **promotes the exact RC image** for that commit to `:1.3.0` and `:latest` — it does not rebuild, so staging and production ship identical bytes. It also checks that the released version has a row in the README roadmap's **Released** table.

   If an RC image is missing for the tagged commit, the release **fails** instead of building one from the tag. A rebuild would look like it worked while quietly shipping bytes nobody validated, differing from staging by whatever moved in the base image or the dependency tree in the meantime. Build the missing RC first (Actions → **Build Images** → Run workflow on that commit), then re-run the release. `allow_rebuild` overrides this for tags old enough that their RC images have been cleaned up.

The version the running app reports comes from the `APP_VERSION` environment variable (set from the image tag at deploy time); running from source, it falls back to `git describe`.

## License

By contributing to Memship, you agree that your contributions will be licensed under the [Elastic License 2.0 (ELv2)](LICENSE).
