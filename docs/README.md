# Memship Documentation

Documentation for **self-hosting operators**, **organization admins**, and **members**.

> **This page is the language index.** The documentation itself lives under one directory per
> language. Pick yours:
>
> - **[Castellano](es/README.md)** — the default language of the published site
> - **[English](en/README.md)**
> - **[Català](ca/README.md)** — the index only; every page it lists is still served in Spanish
>   or English, marked as such

> **Languages.** Every page is published in `es`, `ca` and `en`, addressed by a directory rather
> than a filename suffix: `docs/<locale>/<section>/<page>.md`. `es` is the default, so a Spanish
> page is served without a locale prefix in its URL. Where a language has no translation yet the
> reader is served the next available one, marked as such — coverage is tracked in
> [#423](https://github.com/marcandreuf/memship/issues/423).

## Which version these docs describe

These docs describe memship 3.0.1 — the current release — plus anything merged since it was
tagged. They are published from the main branch, so a change lands here when it is merged rather
than when the next version ships.

**To check what your own instance runs**, ask it:

```bash
curl -s http://localhost/api/v1/health   # {"status":"healthy","version":"2.19.0",...}
```

`version` is the image tag the instance was deployed with. If it reads `latest` you are on an
unpinned install and cannot tell from here — see [Upgrading](en/self-hosting/upgrading.md).

**If your instance is older than the version above**, read the docs as they stood for your
release rather than these. Every tag carries its own copy, so swap the version into the path:

```
https://github.com/marcandreuf/memship/blob/v2.18.0/docs/README.md
```

What changed between your version and this one is on the
[releases page](https://github.com/marcandreuf/memship/releases), where each release's notes carry
the behaviour changes and migrations an upgrader must not miss.


## Project policies

These live at the repository root rather than here, because `docs/` is product
documentation — how memship works and how to run it — and these are the project's own
rules. GitHub also surfaces them from the root on its own.

- [Contributing](https://github.com/marcandreuf/memship/blob/main/CONTRIBUTING.md) — branching, versioning and how a release is cut _(EN)_
- [Code of conduct](https://github.com/marcandreuf/memship/blob/main/CODE_OF_CONDUCT.md) — what is expected of everyone taking part _(EN)_
- [Security policy](https://github.com/marcandreuf/memship/blob/main/SECURITY.md) — reporting a vulnerability privately, and what counts as
  one rather than an ordinary bug _(EN)_
- [Accessibility](https://github.com/marcandreuf/memship/blob/main/ACCESSIBILITY.md) — what the project aims for, what has and has not been
  tested, and how to report a barrier _(EN)_

---

## Contributing to the docs

- **Docs live with the code.** When a feature PR changes behaviour, update its page in the
  same PR. Each admin/member guide page maps 1:1 to a feature module in the app.
- **A page belongs to a locale directory, not to a filename.** `docs/es/admin-guide/sepa.md`,
  never `sepa.es.md`. The suffix form cannot publish two languages of one page, which is why it
  was replaced — see [#446](https://github.com/marcandreuf/memship/issues/446).
- **Link within your own locale by plain relative path**, and across locales by going through the
  directory: from `es/admin-guide/` to an English operator page is
  `../../en/self-hosting/email.md`. A link that resolves on the site through the language
  fallback but not on GitHub is a broken link — the published build rejects it.
- **A translation records what it was translated from**, in a comment block at the top:

  ```markdown
  <!-- source: en/getting-started/what-you-need.md -->
  <!-- source-hash: 9f5a006988a7 -->
  ```

  The hash is the first 12 characters of the source file's git blob id. CI re-hashes the source
  and fails when it has moved on, naming the pages to revisit — otherwise a source page changes
  and its translations become pages that disagree while all three look equally current, the stale
  one hardest to spot in the language its reader cannot check
  ([#451](https://github.com/marcandreuf/memship/issues/451)). A page with no `source:` is itself a
  source and is skipped, so a page is adopted the moment it is translated and not before.

  After re-translating, restamp with `./scripts/check-docs-translations.sh --fix`.
- **Keep heading anchors stable.** Pages link into each other's headings (e.g.
  `settings.md#banca-y-facturación`), the READMEs and the issue templates link in from
  outside the folder, and GitHub does not redirect a renamed anchor. So rename headings
  deliberately and fix what pointed at them — nothing warns you. The app itself does not yet
  link to these pages; when it does, its links will be the ones hardest to find and fix.
- **Plain Markdown, tool-agnostic.** These files render on GitHub today and are published by the
  documentation site without rework. Avoid tool-specific syntax.
