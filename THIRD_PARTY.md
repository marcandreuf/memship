# Third-party notices

Memship contains source code from the projects below, copied into this
repository rather than installed as a dependency. Their licences require their
copyright notices to travel with the code, which is what this file is for.

**Where this lives.** In the repository only. The published Docker images do
not carry a copy: Next's output tracing compiles dependency code into the
bundle and drops their licence files, so a built standalone output holds one
`LICENSE` across roughly 2900 files, and adding this one would need the image
build context moved from `frontend/` to the repository root. The source is
public, so the notices are reachable by anyone who has the image. Worth
revisiting if Memship is ever distributed as a binary artefact on its own.

**Scope.** This file covers code **vendored into the tree**. Dependencies
installed from npm and PyPI are not listed here: they are declared in
`frontend/package.json`, `pnpm-lock.yaml`, `backend/pyproject.toml` and
`backend/uv.lock`, and carry their own licence files in their own packages.

---

## shadcn/ui

Twenty-four of the components under `frontend/components/ui/` were generated
from the shadcn/ui registry and then edited in place. `frontend/components.json`
records the registry configuration, and `cn()` in `frontend/lib/utils.ts` is the
helper that ships with it.

Unlike a dependency, these components are *copied* into the project and
maintained here, so the notice below is the only place their origin is recorded.

```
alert-dialog.tsx   avatar.tsx     badge.tsx      breadcrumb.tsx
button.tsx         card.tsx       checkbox.tsx   dialog.tsx
dropdown-menu.tsx  form.tsx       input.tsx      label.tsx
scroll-area.tsx    select.tsx     separator.tsx  sheet.tsx
sidebar.tsx        skeleton.tsx   sonner.tsx     switch.tsx
table.tsx          tabs.tsx       textarea.tsx   tooltip.tsx
```

Plus `frontend/lib/utils.ts`.

> MIT License
>
> Copyright (c) 2023 shadcn
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

---

## Memship's own components

These live in the same directory and are **not** third-party. They are listed
so that every file under `frontend/components/ui/` is accounted for, and so the
check described below can tell a new vendored component from a new local one.

```
confirm-dialog.tsx      decimal-input.tsx    form-error-summary.tsx
password-input.tsx      skeletons.tsx
```

---

## Keeping this accurate

`scripts/check-attribution.sh` fails if any file under
`frontend/components/ui/` is missing from both lists above. Adding a component
from the shadcn registry, or writing a new one, therefore forces a decision
about which it is rather than leaving the notice quietly incomplete.
