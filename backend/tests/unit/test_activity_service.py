"""Unit tests for activity service slug generation."""

from unittest.mock import MagicMock

from app.domains.activities.service import generate_slug


def _mock_db_no_existing():
    """Return a mock db where no slugs exist."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


class TestSlugGeneration:
    def test_slug_from_simple_name(self):
        db = _mock_db_no_existing()
        result = generate_slug(db, "Summer Camp")
        assert result == "summer-camp"

    def test_slug_from_accented_name(self):
        db = _mock_db_no_existing()
        result = generate_slug(db, "Café d'été")
        assert result == "cafe-d-ete"

    def test_slug_strips_special_chars(self):
        db = _mock_db_no_existing()
        result = generate_slug(db, "Hello! World?")
        assert result == "hello-world"
