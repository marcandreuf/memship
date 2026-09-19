"""The catalogue, the templates and the subjects describe the same set of mails.

``app.domains.mailing.policy.CATALOG`` is what the settings screen renders and
what ``is_enabled`` consults. A key missing from it is not merely unlisted:
``always_sends`` returns True for any key it does not know, so an uncatalogued
template bypasses the opt-in gate entirely and mails members on a fresh install
that never switched anything on (#229).

That is how ``welcome`` sat in the tree — a sender, three subjects and three
rendered templates, no catalogue entry and no callers — waiting for someone to
wire it up. It was removed rather than catalogued; these tests keep the next one
from being added the same way.

``mailing_test`` is the single deliberate omission: it is the settings screen's
own credential check, not a member communication, and must send whatever the
organization has switched off.
"""

import re
from pathlib import Path

import pytest

from app.core.email import _SUBJECTS, _template_dir
from app.domains.mailing.policy import BY_KEY, CATALOG

LOCALES = ("es", "ca", "en")

# Not a member communication — see the module docstring and ``policy.py``.
UNCATALOGUED_BY_DESIGN = frozenset({"mailing_test"})

# The admin writes the subject on the announcement itself, and
# ``send_announcement_email`` passes it to the funnel as a ``subject`` override,
# so there is nothing for ``_SUBJECTS`` to hold. Catalogued all the same: the
# broadcast channel is switchable like any other.
SUBJECT_FROM_CALLER = frozenset({"announcement"})

CATALOGUE_KEYS = sorted(spec.key for spec in CATALOG)


def _template_keys() -> set[str]:
    """Every template key present on disk, from its ES file.

    ES is the default locale and the fallback every other one resolves to, so a
    template that exists at all exists in ES. Files starting with ``_`` are
    Jinja partials (``_base``, ``_components``), not mails.
    """
    return {
        p.name[: -len("_es.html")]
        for p in Path(_template_dir).glob("*_es.html")
        if not p.name.startswith("_")
    }


@pytest.mark.parametrize("key", sorted(_template_keys()))
def test_every_template_on_disk_is_catalogued(key):
    """A template with no catalogue entry sends unconditionally."""
    if key in UNCATALOGUED_BY_DESIGN:
        pytest.skip(f"{key} is uncatalogued by design")
    assert key in BY_KEY, (
        f"templates/email/{key}_es.html has no TemplateSpec. Add one to CATALOG "
        f"in app/domains/mailing/policy.py, or delete the template — an "
        f"uncatalogued key bypasses the organization's opt-in gate."
    )


@pytest.mark.parametrize("key", CATALOGUE_KEYS)
@pytest.mark.parametrize("locale", LOCALES)
def test_every_catalogued_key_has_a_template(key, locale):
    assert (Path(_template_dir) / f"{key}_{locale}.html").is_file()


@pytest.mark.parametrize("key", CATALOGUE_KEYS)
def test_every_catalogued_key_has_a_subject_in_every_locale(key):
    if key in SUBJECT_FROM_CALLER:
        assert key not in _SUBJECTS, (
            f"{key} now has a catalogue subject — drop it from SUBJECT_FROM_CALLER"
        )
        pytest.skip(f"{key} carries a caller-supplied subject")
    assert key in _SUBJECTS, f"{key} is catalogued but has no _SUBJECTS entry"
    assert set(_SUBJECTS[key]) >= set(LOCALES), (
        f"{key} is missing a subject in {sorted(set(LOCALES) - set(_SUBJECTS[key]))}"
    )


@pytest.mark.parametrize("key", sorted(_SUBJECTS))
def test_every_subject_belongs_to_a_catalogued_key(key):
    """Catches a sender added with its subject but no catalogue entry."""
    if key in UNCATALOGUED_BY_DESIGN:
        pytest.skip(f"{key} is uncatalogued by design")
    assert key in BY_KEY, f"_SUBJECTS['{key}'] has no TemplateSpec in CATALOG"


def test_the_only_uncatalogued_template_is_the_settings_credential_check():
    """The exception list is exact — a second one must be argued for, not added."""
    assert _template_keys() - set(BY_KEY) == set(UNCATALOGUED_BY_DESIGN)


def test_welcome_is_gone():
    """Removed in #229. Re-adding it needs a catalogue entry and a call site."""
    assert "welcome" not in _template_keys()
    assert "welcome" not in _SUBJECTS
    source = (Path(__file__).resolve().parents[2] / "app" / "core" / "email.py").read_text(
        encoding="utf-8"
    )
    assert not re.search(r"\bdef send_welcome_email\b", source)
