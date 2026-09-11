# Contributing to Memship

Thank you for your interest in contributing to Memship!

## Current Status

Memship is in active development. The foundation — infrastructure, CI/CD, and core architecture — is in place, and **code contributions are welcome**. See [Releases](README.md#releases) for what has shipped and the [roadmap](README.md#roadmap) for what is planned.

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

- `main` is the single long-lived branch. It is what releases are cut from, and what the deployed instance runs a released image of.
- All work happens on **short-lived `feature/*` branches** taken from `main` and merged back through a pull request.
- Every push to `main` builds **release-candidate images**. A release promotes one of them; it never builds a new one.

**There are no long-lived environment branches** — no `develop`, `integration`, `preproduction`, `release/*`, or `hotfix/*`. GitHub Flow deliberately rejects the multi-branch Git Flow model: at this team size its ceremony is overhead, and in Git Flow `develop` *is* the integration branch, so a separate `develop` **and** `integration` (or `preproduction`) branch is redundant. One trunk avoids the question entirely.

#### Branches vs. environments

Environments are targets you deploy an image *to*; they do not each need a matching branch. So there is nothing to "prepare" as a `preproduction` branch — and in this project there is nothing to prepare it *for*:

| Environment | What deploys there | Trigger |
|---|---|---|
| **`production`** | a released image, `:X.Y.Z` — the RC built from `main`, re-tagged, never rebuilt | a maintainer runs the **Deploy** workflow by hand |

**There is exactly one environment, and no pre-production one.** `staging.openmemship.com` is its hostname, which is historical and misleading: that host *is* production. The repository has a single GitHub Environment, named `production`, and `deploy.yml` runs on `workflow_dispatch` only — nothing deploys automatically, on a merge or on a tag.

What stands in for a staging gate is that production's only users are the maintainers, who explore a release there before it is announced. Accept what that does and does not buy you: CI and the E2E suite are the real gate, and a release that turns out to be wrong is superseded by the next patch version rather than rolled back in place. See [Releases](#releases) below for the promote flow.

### Getting Started

1. Fork the repository (or, if you have push access, clone it directly)
2. Create a `feature/*` branch from `main`
3. Make your changes
4. Run the tests to ensure nothing is broken
5. Open a pull request against `main`

### Development Setup

**Prerequisites:** Docker + Docker Compose, and Node.js 22+ with [pnpm](https://pnpm.io) for the frontend. The backend — including its test suite — runs entirely in containers, so there is no host Python to install.

The backend (API, PostgreSQL, Redis, Celery worker and beat) runs in Docker; the frontend runs locally with pnpm. One script manages all of it:

```bash
./scripts/dev.sh start all     # Start backend (Docker) + frontend (local)
./scripts/dev.sh status        # Show what is running
./scripts/dev.sh stop all      # Stop everything
```

Enable the repository's hooks once per clone (git does not distribute them):

```bash
git config core.hooksPath .githooks
```

Then seed the database with test accounts:

```bash
./scripts/dev.sh seed test     # Creates test accounts and sample data, no prompts
```

The app is at http://localhost:3000 and the API docs at http://localhost:8003/api/docs. Log in with `admin@examplee6e3b1.com` / `TestAdmin1!`.

Run the backend tests with `./scripts/dev.sh test` — they run in a throwaway container against a tmpfs database, and anything after `test` is passed straight to pytest (`./scripts/dev.sh test tests/unit -x`).

See the [Development section of the README](README.md#development) for the full command reference, service URLs, and the rest of the seeded test accounts.

> **Note:** Python dependencies are installed into the image's virtualenv at build time. After adding or upgrading a backend dependency, rebuild or the running containers will not have it — the test container builds a different stage, so it needs its own:
>
> ```bash
> docker compose -f backend/docker/docker-compose.yml build --no-cache api
> docker compose -f backend/docker/docker-compose.yml up -d --force-recreate api celery-worker celery-beat
> docker compose -f backend/docker/docker-compose.yml --profile test build tests
> ```

### Commit Messages

- Use clear, descriptive commit messages
- Start with a verb in imperative mood (e.g., "Add member search endpoint")
- Keep the first line under 72 characters
- **Every commit is authored by a human maintainer.** If an AI assistant helped, record it with a
  plain `Assisted-by:` line — never `Co-Authored-By:`, which GitHub reads as a real contributor and
  lists in the repository's Insights graph beside the maintainers:

  ```
  Assisted-by: Claude Code (claude-opus-5)
  ```

  The `commit-msg` hook in `.githooks/` enforces this: it strips an assistant `Co-Authored-By:` (and
  the `Claude-Session:` URL some tools add) and substitutes the `Assisted-by:` line. A human
  co-author is never touched — keep crediting people that way.

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

Because features are built in parallel, **the number is claimed at release, not when you branch.** Whoever releases first takes the next number; the next feature to ship takes the one after — so don't hard-code a target version into your branch, commits, or the roadmap while the work is in flight. When your feature is ready, add its row to the [release table](README.md#releases) *in the same PR as the feature code*, then tag. That is also what satisfies the release guard (step 4 below): the tagged commit must already carry the released version's README row.

The flow is **build once, promote**:

1. A PR merges to `main`. CI runs, then the Build Images workflow pushes **release-candidate images** tagged `sha-<commit>` and `main` to GHCR. **Every service is built on every commit**, even one it did not touch, so each commit on `main` has a complete RC set and any of them can be released.
2. CI must be green on that exact commit, and the Build Images run for it must have succeeded — a release can only promote an RC that exists.
3. To release the validated commit, a maintainer tags it and pushes the tag:

   ```bash
   ./scripts/release.sh 1.3.0          # tags HEAD (must be a validated commit on main)
   ./scripts/release.sh 1.3.0 <sha>    # or tag a specific validated commit
   ```

   This creates an annotated `v1.3.0` tag and pushes it.
4. The Release workflow **promotes the exact RC image** for that commit to `:1.3.0` and `:latest` — it does not rebuild, so what ships is the bytes CI tested. It also checks that the released version has a row in the README's [release table](README.md#releases), and drafts the GitHub release seeded from that row.

   If an RC image is missing for the tagged commit, the release **fails** instead of building one from the tag. A rebuild would look like it worked while quietly shipping bytes nothing had tested, differing from the RC by whatever moved in the base image or the dependency tree in the meantime. Build the missing RC first (Actions → **Build Images** → Run workflow on that commit), then re-run the release. `allow_rebuild` overrides this for tags old enough that their RC images have been cleaned up.

5. A maintainer deploys it: Actions → **Deploy** → `target: production`, `version: 1.3.0`, leaving `ref` empty. This is manual and always has been — every deploy this project has run has been of a released version.
6. Explore the deployed instance, then finish and publish the drafted release notes. The images are already live either way, so an unpublished draft is a missing announcement, not a blocked release.

`ref` is the escape hatch beside `version`: it deploys `sha-<commit>` for a commit with no tag, for the rare case where you want the instance on an RC without claiming a version number. Set one input or the other, never both.

The version the running app reports comes from the `APP_VERSION` environment variable (set from the image tag at deploy time); running from source, it falls back to `git describe`.

## License

By contributing to Memship, you agree that your contributions will be licensed under the [Elastic License 2.0 (ELv2)](LICENSE).
