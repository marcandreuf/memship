"""The constant-work half of #102.

`/register` and `/login` both answer a known and an unknown address the same
way. That only holds while they also *cost* the same: argon2 is slow on
purpose, so a path that skips it returns sooner and reports the address by the
clock instead of the response body.

Timing is not asserted here — a wall-clock threshold is the kind of test that
fails on a loaded CI box and teaches everyone to rerun it. What is asserted is
the property the timing follows from: every path that returns without a real
verification spends a decoy one first.
"""

from app.core.security import password as pw


class TestSpendVerifyWork:
    def test_nothing_verifies_against_the_decoy(self):
        assert pw.verify_password("whatever", pw.decoy_hash()) is False

    def test_it_swallows_the_mismatch_rather_than_raising(self):
        assert pw.spend_verify_work("whatever") is None

    def test_the_decoy_carries_the_same_parameters_as_a_real_hash(self):
        """Equal cost is the whole point, and the cost is in the parameters."""
        real = pw.ph.hash("password123")
        assert real.split("$")[:4] == pw.decoy_hash().split("$")[:4]

    def test_the_decoy_is_rebuilt_when_the_hasher_is_replaced(self, monkeypatch):
        """The integration suite swaps in cheap parameters. A decoy held over
        from the production hasher would cost minutes across a run, and would
        no longer match what it is standing in for."""
        from argon2 import PasswordHasher

        first = pw.decoy_hash()
        assert pw.decoy_hash() is first  # stable while the hasher is

        monkeypatch.setattr(
            pw, "ph", PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1)
        )
        rebuilt = pw.decoy_hash()

        assert rebuilt != first
        assert "m=8192" in rebuilt
