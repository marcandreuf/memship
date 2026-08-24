# Security Policy

## Reporting a vulnerability

**Please do not open a public issue for a security vulnerability.**

Report it through GitHub's private vulnerability reporting, which is enabled on this repository:

**[Report a vulnerability](https://github.com/marcandreuf/memship/security/advisories/new)**

That opens a private conversation visible only to you and the maintainers. If you cannot use it,
email <marcandreuf@gmail.com> with `memship security` in the subject.

Useful things to include, as far as you have them: what an attacker can do, the affected version or
commit, the file and line if you have read the code, and the steps to reproduce. A proof of concept
helps but is not required — a clear description of the code path is enough to start.

You should get an acknowledgement within a few days. We will tell you what we found, whether we
agree on the severity, and when a fix is expected. If we disagree that something is a vulnerability
we will explain why rather than closing silently.

## What counts

Anything that lets someone read, change or destroy data they should not reach: authentication and
session handling, the permission model, file uploads and downloads, SQL injection, SSRF, secrets
appearing where they should not, and the payment and SEPA paths.

Bugs that cost money or corrupt records without an attacker — a batch total that disagrees with the
file, a double-booking race — are ordinary bugs. **Open a normal issue for those.** They are tracked
publicly, and being public is how contributors find and fix them.

If you are unsure which one you have, report it privately. We would rather move something into the
open tracker than have it sit in a public issue while it is still exploitable.

## Supported versions

Pre-1.0, only the latest release receives fixes. Upgrade before reporting if you are behind — see
[Upgrading](docs/self-hosting/upgrading.md).

## Disclosure

We fix in a private fork, release a patched version, then publish the advisory crediting the
reporter unless they prefer otherwise. If a report is already public or being exploited, we will say
so and move faster.

Please give us a reasonable window to ship a fix before publishing. We are a small project and will
be honest with you about timelines rather than stalling.

## A note on what this software holds

memship is self-hosted, so an operator's install holds their members' names, addresses, contact
details, and — where SEPA is used — IBANs and signed mandates. A vulnerability here is not abstract.
That is why the reporting path above is private by default, and why we would rather hear about
something uncertain than not hear about it.
