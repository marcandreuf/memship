"""Exported cells must never open as formulas.

The admin exports carry member-supplied text (names, notes) into a
spreadsheet, and a cell starting with ``=``, ``+``, ``-`` or ``@`` is evaluated
by Excel and LibreOffice when the file is opened. A leading apostrophe marks
the cell as text.
"""

import csv
import io
from decimal import Decimal

import pytest

from app.core.csv_export import iter_csv


def _rows(headers, rows):
    text = "".join(iter_csv(headers, rows)).lstrip("﻿")
    return list(csv.reader(io.StringIO(text)))


@pytest.mark.parametrize(
    "payload",
    [
        "=1+1",
        "=HYPERLINK(\"http://evil.example\",\"click\")",
        "+cmd|' /C calc'!A0",
        "-2+3",
        "@SUM(A1:A2)",
        "\t=1+1",
        "\r=1+1",
    ],
)
def test_formula_triggers_are_prefixed_with_an_apostrophe(payload):
    _, row = _rows(["notes"], [[payload]])
    assert row == ["'" + payload]


def test_ordinary_text_is_untouched():
    _, row = _rows(["name", "email"], [["María García-López", "m@example.com"]])
    assert row == ["María García-López", "m@example.com"]


def test_a_trigger_inside_the_cell_is_not_a_trigger():
    _, row = _rows(["notes"], [["a = b + c"]])
    assert row == ["a = b + c"]


def test_non_string_values_are_written_as_is():
    _, row = _rows(["id", "amount", "empty"], [[7, Decimal("-12.50"), None]])
    assert row == ["7", "-12.50", ""]


def test_headers_are_not_touched():
    headers, _ = _rows(["=id"], [["x"]])
    assert headers == ["=id"]
