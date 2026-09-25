"""Free-text search over several columns."""

from sqlalchemy import and_, or_, true
from sqlalchemy.sql.elements import ColumnElement


def _escape_like(word: str) -> str:
    return word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def match_words(text: str, *columns) -> ColumnElement[bool]:
    """Every word of ``text`` must appear, case-insensitively, in one of
    ``columns``.

    Matching the whole string against each column separately misses what the
    lists display: "Aina Torrent" is in no single column, but "Aina" is in
    ``first_name`` and "Torrent" in ``last_name``. Word order does not matter,
    and ``%`` / ``_`` are matched literally rather than as wildcards.
    """
    words = text.split()
    if not words:
        return true()
    return and_(
        *(
            or_(*(col.ilike(f"%{_escape_like(w)}%", escape="\\") for col in columns))
            for w in words
        )
    )
