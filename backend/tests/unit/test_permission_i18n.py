"""The catalog and the translation files must not drift apart.

41 permissions x 2 strings x 3 locales is exactly the surface where one locale
lags silently: a missing key renders as the raw key in the role editor, which
is the screen a super admin uses to decide what to grant.
"""

import json
from pathlib import Path

import pytest

from app.core.permissions import CATALOG

LOCALES = ("es", "ca", "en")
LOCALES_DIR = Path(__file__).resolve().parents[3] / "frontend" / "locales"


def _load(locale: str) -> dict:
    return json.loads((LOCALES_DIR / locale / "roles.json").read_text(encoding="utf-8"))


def _resolve(messages: dict, dotted: str) -> str | None:
    """next-intl reads a dot as a nesting level, so `permissions.members.read.label`
    is a path — this walks it the same way the client does."""
    node = messages
    for segment in dotted.split("."):
        if not isinstance(node, dict) or segment not in node:
            return None
        node = node[segment]
    return node if isinstance(node, str) else None


@pytest.mark.parametrize("locale", LOCALES)
def test_every_permission_has_a_label_and_a_description(locale: str):
    messages = _load(locale)
    missing = [
        key
        for permission in CATALOG
        for key in (permission.label_key, permission.description_key)
        if not _resolve(messages, key)
    ]
    assert not missing, f"{locale}: missing {len(missing)} strings: {missing[:10]}"


def test_locales_hold_the_same_keys():
    def flatten(node, prefix=""):
        for key, value in node.items():
            if isinstance(value, dict):
                yield from flatten(value, f"{prefix}{key}.")
            else:
                yield f"{prefix}{key}"

    reference = set(flatten(_load("es")))
    for locale in LOCALES[1:]:
        other = set(flatten(_load(locale)))
        assert reference == other, (
            f"{locale} differs: missing {sorted(reference - other)}, "
            f"extra {sorted(other - reference)}"
        )


def test_no_permission_carries_a_stale_translation():
    """A key with no catalog entry behind it grants nothing and misleads the
    author reading the editor."""
    messages = _load("es")["permissions"]

    def flatten(node, prefix=""):
        for key, value in node.items():
            if isinstance(value, dict):
                yield from flatten(value, f"{prefix}{key}.")
            else:
                yield f"{prefix}{key}"

    translated = {key.rsplit(".", 1)[0] for key in flatten(messages)}
    assert translated == {permission.key for permission in CATALOG}