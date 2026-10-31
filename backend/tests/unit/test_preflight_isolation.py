"""One unrunnable check must not take the whole gate down.

memship#476 was not that a check was wrong. It was that a single check raising
aborted the comprehension that ran all of them, so the gate reported "the
checks could not be run" with no way to tell which one, and `scripts/upgrade.sh`
turned that into a refusal of every upgrade from 3.0.0.

Resolving the pending range removed that trigger. It did not change the shape:
any future check that raises still takes every other check with it. These tests
pin the shape instead of the instance.

The exit code deliberately does not soften. A check that could not run still
refuses, because being unable to look is not the same as having looked. What
isolation buys is the operator knowing *which* check broke and that the others
were consulted.

Pure logic, so the connection is a stand-in: whether a failed statement leaves
the next check a usable connection is a question about Postgres, and is pinned
by the integration test beside the CLI.
"""

from contextlib import nullcontext

import pytest
import sqlalchemy as sa

from app.cli.preflight import evaluate


class _StubEngine:
    """Hands out a throwaway connection object per check, like the real one."""

    def __init__(self):
        self.handed_out = 0

    def connect(self):
        self.handed_out += 1
        return nullcontext(object())


def _passes(_conn):
    return None


def _refuses(_conn):
    return "two accounts hold one address"


def _cannot_run(_conn):
    raise sa.exc.ProgrammingError("SELECT members.user_id", {}, Exception("no column"))


class TestOneBrokenCheckDoesNotHideTheRest:
    def test_a_check_after_the_broken_one_still_reports(self):
        blocks, unrunnable = evaluate(
            _StubEngine(),
            [("aaa", _passes), ("bbb", _cannot_run), ("ccc", _refuses)],
        )

        assert [revision for revision, _ in blocks] == ["ccc"]
        assert [revision for revision, _ in unrunnable] == ["bbb"]

    def test_the_broken_check_is_named_by_its_revision(self):
        """The old message named none of them, which is what made it unusable:
        an operator could not tell a data problem from a bug in our code."""
        _, unrunnable = evaluate(_StubEngine(), [("bbb", _cannot_run)])

        revision, detail = unrunnable[0]
        assert revision == "bbb"
        assert "no column" in detail

    def test_every_check_is_consulted(self):
        engine = _StubEngine()

        evaluate(engine, [("aaa", _passes), ("bbb", _cannot_run), ("ccc", _refuses)])

        assert engine.handed_out == 3

    def test_nothing_to_report_when_every_check_passes(self):
        blocks, unrunnable = evaluate(
            _StubEngine(), [("aaa", _passes), ("ccc", _passes)]
        )

        assert blocks == []
        assert unrunnable == []


class TestOnlyDatabaseErrorsAreTreatedAsUnrunnable:
    def test_a_programming_mistake_in_a_check_is_not_swallowed(self):
        """A check raising TypeError is our bug, not an unrunnable check.
        Reporting it as "could not run" would bury it behind a message that
        reads like an operator problem."""

        def _broken_python(_conn):
            raise TypeError("check takes no argument")

        with pytest.raises(TypeError):
            evaluate(_StubEngine(), [("aaa", _broken_python)])
