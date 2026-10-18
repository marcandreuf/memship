# Accessibility

memship manages people's membership of a club or association: their registrations, their
receipts, their bank mandate, the card they show at the door. If the software cannot be used
with a keyboard or a screen reader, then someone has to do those things on another person's
behalf — which, for a payment or a signed mandate, is not an acceptable substitute. The
people who need to reach it are both sides of the organization: the staff who run it and the
members who look at their own data.

This document says what the project aims for, what contributors are expected to do, how to
report a barrier, and — the part that matters most when you have just hit one — what has
actually been tested and what has not. It is deliberately specific about the gaps. memship is
a pre-1.0 project with one maintainer; an accessibility statement that implied more coverage
than exists would waste the time of the person reading it.

## Priorities

**There is no conformance claim here.** No accessibility evaluation has been carried out on
memship — no audit, no assistive-technology testing, no automated scan in CI. WCAG 2.2 AA is
the standard the project works toward and is an **aspirational goal, not a verified result.**
If and when an evaluation happens, this section will name its scope, date, method and
evaluator; until it does, treat anything below as intent plus what can be read off the code.

What gets priority, in this order:

- **Keyboard operation of the core tasks.** Logging in, finding a member, registering for an
  activity, paying a receipt. A task that can only be completed with a pointer is a defect,
  not a limitation.
- **Things having names.** Every control should say what it is and every field should be tied
  to its label, its hint and its error. Forms go through one wrapper
  (`frontend/components/ui/form.tsx`), which sets `aria-describedby` and `aria-invalid` from
  the field's validation state, so this is mostly a matter of not working around it.
- **A non-visual path to the same information.** Where the interface is graphical — the QR
  member card, the dashboard charts — there should be a way to the same facts that does not
  require seeing or aiming a camera. The scanner already has one (see below); the charts do
  not.
- **Language.** All user-facing text comes from translation files, never hardcoded, in Spanish
  (default), Catalan and English, currently at full key parity. `<html lang>` is set from the
  active locale, so screen readers get the right pronunciation rules.
- **Not relying on colour alone.** Status is rendered as a badge with a word in it. Light and
  dark themes are both first-class, as is the system-preference default.

The interface is built on Radix primitives (via Shadcn/ui, copied into
`frontend/components/ui/`), so dialogs, menus, selects, tabs and the sidebar arrive with
focus management, roles and keyboard interaction already implemented. That is a good
starting position and not a guarantee: the copies are edited in this repo like any other
code, and nothing currently checks whether an edit broke them.

## Contributor expectations

There is no automated accessibility gate. CI runs backend pytest, lint, and the Cypress E2E
suite; it does **not** run axe-core, pa11y, Lighthouse or any equivalent, and none of those
are project dependencies. So the expectations below are human ones, and the review is a human
reading the PR.

For any change to the frontend:

- **Drive it with the keyboard before opening the PR.** Tab to the control you added, operate
  it, and get back out. Say in the PR description that you did. If focus gets trapped
  somewhere, or an action is reachable only by clicking a row or a cell, that is the finding —
  report it even if you cannot fix it.
- **Reach for the existing primitive.** A new interactive control should be a `Button`, a
  `Select`, a `Dialog` from `components/ui/`, not a `div` with an `onClick`. When you do need
  something custom, the keyboard behaviour is yours to implement and yours to describe.
- **Give every control an accessible name, and use the form wrapper for fields.** An icon-only
  button needs an `aria-label`; the text inside it must come from the translation files, in all
  three locales — an `aria-label` with a hardcoded English string is a bug in the Spanish UI
  that nothing visible will reveal.
- **Images need a decision, not a default.** Meaningful images get real alt text (member
  photos use the person's name, the organization logo uses its name); decorative ones get
  `alt=""` deliberately.
- **If you change the two entity shells, you change every page.** Lists and detail pages are
  assembled from `components/entity/`, so a keyboard or naming fix there fixes the whole app —
  and a regression there breaks the whole app.

One incidental safety net worth knowing about: the E2E suite selects elements by their
accessible names (`button[aria-label="Pay Now"]`, `nav[aria-label='breadcrumb']`). Deleting a
label often fails a test. This is a side effect of how the specs were written, not an
accessibility check — it catches removals, never anything else.

## Reporting accessibility issues

**Open a public issue:
[github.com/marcandreuf/memship/issues](https://github.com/marcandreuf/memship/issues)**, and
say in the title that it is an accessibility barrier. The form that opens is the project's
general bug-report template — fill in what is relevant and delete the rest. Its screenshot
and device fields are prompts, not requirements; plain prose is fine, and so is a one-line
report.

**If GitHub itself is the barrier, email <marcandreuf@gmail.com>** with `memship
accessibility` in the subject. A report that arrives by email is treated exactly like an
issue — the maintainer will open the issue for you and tell you its number, or keep the whole
thing in email if you prefer. Do not let the reporting channel be the reason something goes
unreported.

Useful context, as much or as little of it as you have:

- what you were trying to do, and where you got stuck
- the page or URL, and whether you were in the admin panel or the member portal
- what happened, and what you expected instead
- browser and version, operating system, and any assistive technology — including its version
  and settings, if that is easy to say
- the memship version (shown in the app) and the interface language

**Screenshots and recordings are welcome but never required**, and neither is any explanation
of why you use the technology you use. Do not tell us anything about your disability; it is
not needed to fix a bug, and it is not wanted here.

### Severity

Assigned by the maintainer during triage — **as a reporter you never need to pick one**, and
getting it "wrong" costs nothing.

- **Blocking** — a task cannot be completed at all by this route. A member cannot log in with
  a keyboard; a form cannot be submitted with a screen reader; a required field's error is
  never announced, so the form can never be corrected. These are treated as release-blocking
  defects.
- **Serious** — the task can be completed, but only through a workaround that costs real
  effort or needs someone else's help. A dialog that does not return focus, so you have to tab
  through the page again; a table whose meaning only arrives by reading the colour of a cell
  alongside a text badge.
- **Moderate** — the task works and is self-service, but the experience is worse than it
  should be. A missing heading level, a focus outline that is hard to see, an unhelpful
  accessible name on a control whose purpose is clear from context.

A barrier on a payment, a SEPA mandate or login is weighted up a level: those are the paths
where being unable to proceed cannot be worked around inside the product.

### How we respond

What the project can genuinely promise, which is less than a company can:

- **An acknowledgement within a few days**, and an honest answer about whether it is a bug we
  understand or a limitation we already know about.
- **A workaround if one exists**, stated in the issue as soon as we know of one — including
  "do this part on a desktop browser instead" or "ask an admin to do it for you", if that is
  the truth today.
- **Fixes land in the next release.** Pre-1.0, only the latest release gets fixes, so an
  upgrade is how a fix reaches your install — see
  [Upgrading](docs/self-hosting/upgrading.md). Blocking barriers are aimed at the next patch;
  anything else is scheduled honestly rather than promised by a date.
- **You get asked to confirm it.** Accessibility fixes are easy to get wrong from the outside,
  so when one ships we will ask whether it actually works for you, and reopen if it does not.
  You are welcome to decline.
- **No silent closures.** If something is not going to be fixed soon, the issue says so and
  stays open. If we disagree that something is a barrier, we explain why.

## Ownership and maintenance

memship has a single maintainer, who owns accessibility along with everything else: triage,
severity, the fixes, and this document. Nothing here is delegated to a committee that does
not exist.

The practical review point is the release cycle. Every release is explored by hand on the
deployed instance before it is announced, and that pass is where accessibility regressions
are expected to be caught today — which also means it is as good as one person's pass can be.
This statement is reviewed when that exploration or a report invalidates something in it, and
at the latest at each minor release. If maintainership changes or grows, this section is
updated in the same change as the handover, and the reporting addresses above move with it.

## Supported environments

Being precise about this, because "supported" and "tested" are not the same thing:

**Automated coverage** is the Cypress E2E suite: headless Chromium, one viewport
(1280×720), pointer-driven. It exercises the product's flows, not its accessibility.

**Tested by hand** before a release: a current Chromium-based desktop browser on Linux, and
the same browser at phone widths. Keyboard and mouse.

**Expected to work, not verified:** current versions of Firefox and Safari on desktop, and
mobile Safari and Chrome on real phones and tablets. The stack (Next.js 15, React 19,
Tailwind 4) targets current evergreen browsers, and nothing in it is Chromium-specific — but
nobody has sat down with these and checked, so a browser-specific bug would reach you before
it reached us. Report it.

**Not evaluated at all:** screen readers (NVDA, JAWS, VoiceOver, TalkBack, Orca), voice
control, switch access, screen magnification, browser zoom beyond incidental use, and
Windows high-contrast mode. No claim is made about any of them, in either direction. The
absence of a claim is not a claim of absence — it means nobody knows yet.

**Server side**, which affects nothing about this document but is asked often: Docker and
Docker Compose on Linux, per the [installation guide](docs/getting-started/installation.md).

## Known limitations

Read off the current code and the testing above. This list is what is known, not what exists.

- **There is no "skip to content" link.** Reaching the main area of a page by keyboard means
  tabbing through the sidebar navigation on every page. Workaround: the sidebar is
  collapsible, and a screen reader's landmark or heading navigation will jump past it.
- **The dashboard and annual-summary charts have no text or table equivalent.** The monthly
  series exists only inside the chart graphic, so it is unavailable to a screen reader. The
  headline figures beside each chart are real text, and list pages offer a CSV export that
  contains the underlying records — but neither reproduces the chart's series. Tracked as a
  gap to fix by rendering the series as a table.
- **Generated PDFs are untagged.** Receipts, SEPA mandates and the printable member card are
  produced without document structure, so a screen reader gets a flat run of text with no
  headings, no table semantics and no reading order guarantee. Equivalent access: every
  receipt is also on screen in the member portal as ordinary HTML, and admins can export
  receipt data as CSV. The PDF generator does support a tagged variant; enabling it is a
  tracked fix, not a redesign.
- **The bookings week calendar is a plain grid of cells.** It has no grid semantics and no
  arrow-key navigation, so a keyboard user tabs through every bookable slot in reading order
  and a screen reader gets no row/column context — the time and the space have to be inferred
  from the surrounding text. The cells themselves are real buttons and the booked/waitlisted
  state is a worded badge rather than a colour, so booking is possible by keyboard; it is
  tedious. Workaround: a space's slots can also be reached from the space's own page.
- **The QR member card depends on a camera**, which rules it out for some people and in some
  lighting. Equivalent access exists and is not a workaround we invented after the fact: the
  scan panel has a labelled text field for typing the card code by hand, and it performs the
  same check.
- **Nothing automatically checks for regressions.** Any of the priorities above can break in a
  PR and reach a release unnoticed. This is the most significant limitation on the list, and
  the one behind the honesty of the rest of it.
- **Catalan and English member documentation is incomplete.** The admin and member guides are
  Spanish-first; some pages exist only in Spanish, which is a barrier for anyone who reads the
  interface in another language and then needs the manual. The interface itself is fully
  translated.

## Feedback and improvements

**Hit a barrier?** Use [Reporting accessibility issues](#reporting-accessibility-issues)
above — that is the path that gets something fixed.

**Think this document is wrong, overclaiming, or missing something?** That is worth an issue
too, or a pull request against this file. Corrections are especially welcome from people who
use assistive technology, since nearly everything above is inference from code rather than
observation of use. A sentence telling us that a "workaround" is not usable in practice is
more valuable than a polite report, and it will be believed.

Suggestions about practice rather than this text — an automated check worth adding, a testing
setup worth adopting, a priority in the wrong order — belong in an issue as well. Before the
project claims any level of conformance it needs an actual evaluation; if you do accessibility
work and would consider looking at memship, say so.
