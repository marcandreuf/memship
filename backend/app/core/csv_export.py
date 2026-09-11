"""CSV export helpers — stream a CSV file from a lazy row iterator.

Used by the admin ``export.csv`` endpoints. Rows are produced on demand so a
caller can feed a ``query.yield_per(...)`` iterator without materialising the
whole result set in memory. The file is UTF-8 with a BOM so Excel opens it with
the correct encoding.
"""

import csv
import io
from collections.abc import Iterable, Iterator
from typing import Any

from fastapi.responses import StreamingResponse

# Byte-order mark: makes Excel detect UTF-8 instead of the system code page.
_BOM = "﻿"

# A cell starting with one of these is evaluated as a formula by Excel and
# LibreOffice when the file is opened, and the exports carry member-supplied
# text (names, notes) straight into an admin's spreadsheet. A leading
# apostrophe is the spreadsheet convention for "this is text" and defuses it.
# Tab and carriage return are included because a cell beginning with either is
# trimmed before the check, exposing whatever comes next.
_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _defuse(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(_FORMULA_TRIGGERS):
        return "'" + value
    return value


def iter_csv(headers: list[str], rows: Iterable[Iterable[Any]]) -> Iterator[str]:
    """Yield CSV text a row at a time (header row first, prefixed with the BOM)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    def flush() -> str:
        value = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return value

    writer.writerow(headers)
    yield _BOM + flush()

    for row in rows:
        writer.writerow([_defuse(value) for value in row])
        yield flush()


def stream_csv(
    headers: list[str],
    rows: Iterable[Iterable[Any]],
    filename: str,
) -> StreamingResponse:
    """Build a streaming ``text/csv`` attachment response."""
    return StreamingResponse(
        iter_csv(headers, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
