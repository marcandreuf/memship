"""A token that is signed but unusable is a 401, not a 500.

`int(payload["sub"])` turned a missing or non-numeric subject into a KeyError or
ValueError escaping the dependency, so the caller saw a server fault where the
honest answer is an authentication failure — and 5xx noise in anything watching
error rates.
"""

import pytest

from app.core.security.dependencies import _subject_id


class TestSubjectId:
    def test_reads_a_numeric_subject(self):
        assert _subject_id({"sub": "42"}) == 42

    def test_accepts_an_integer_subject(self):
        assert _subject_id({"sub": 42}) == 42

    def test_missing_subject_is_none(self):
        assert _subject_id({}) is None

    def test_null_subject_is_none(self):
        assert _subject_id({"sub": None}) is None

    def test_non_numeric_subject_is_none(self):
        assert _subject_id({"sub": "not-a-user-id"}) is None

    def test_structured_subject_is_none(self):
        """A well-formed JWT can still carry the wrong shape here."""
        assert _subject_id({"sub": {"id": 42}}) is None

    @pytest.mark.parametrize("value", ["", " ", "4 2", "42.5", "0x2a"])
    def test_other_unusable_subjects(self, value):
        assert _subject_id({"sub": value}) is None
