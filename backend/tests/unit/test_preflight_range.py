"""Which checks a given upgrade should consult.

`app.cli.preflight` ran every check it could find against every database,
forever. Its own docstring named the condition that would make that wrong:
"Revisit that when a check appears that would fail against a database its
migration already upgraded." `f5a6b7c8d9e0`'s check reads `members.user_id`,
`29a3872dad10` drops it, and the assumption that an applied check "passes by
construction" turned into an exception that took the whole gate down
(memship#476).

These tests are unit tests against the real revision tree: resolving a range is
a question about the migration graph, not about a database, so no connection is
involved. The graph is a DAG rather than a chain, and the merge revision in it
is the reason hand-parsing `down_revision` is not an option.
"""

from app.cli.preflight import pending_checks, pending_revisions

# v2.19.0's head and the head of the party chain.
BASE_2_19 = "d6f0e949ffef"
PARTY_HEAD = "7b3c9e2a4d51"

# The only two revisions in the tree that declare a preflight_check. Both sit
# well below BASE_2_19, which is why the 3.0.0 upgrade's gate was vacuous.
EMAIL_CASE_CHECK = "f5a6b7c8d9e0"
EMAIL_WHITESPACE_CHECK = "7c1e2d3f4a5b"

# A merge revision and its two parents. Nothing else in the tree has two.
MERGE = "120971684ed2"
MERGE_PARENTS = ("b3c4d5e6f7a8", "f0a1b2c3d4e5")


class TestTheRangeIsResolvedThroughTheGraph:
    def test_a_range_spanning_the_merge_reaches_both_parents(self):
        """The one case hand-parsing `down_revision` gets wrong: following a
        single parent silently drops an entire leg of the graph, and every
        check on that leg stops being consulted.

        `current=None` means "from the base" here, which is alembic's own
        convention for the lower bound. Treating an unmigrated database as
        having nothing to check is a policy decision, so it lives in
        `pending_checks`, not in the graph walk.
        """
        revisions = pending_revisions(None, MERGE)

        for parent in MERGE_PARENTS:
            assert parent in revisions, f"{parent} unreachable through the merge"

    def test_nothing_is_pending_when_the_database_is_already_at_the_target(self):
        assert pending_revisions(PARTY_HEAD, PARTY_HEAD) == []

    def test_an_applied_check_is_not_consulted(self):
        """The defect, stated as a range: upgrading from 2.19.0 onwards must
        not reach a check whose migration is already applied."""
        revisions = pending_revisions(BASE_2_19, PARTY_HEAD)

        assert EMAIL_CASE_CHECK not in revisions
        assert EMAIL_WHITESPACE_CHECK not in revisions

    def test_a_pending_check_is_consulted(self):
        """The guard on over-correcting: a check below the target but above the
        current revision is exactly what the gate is for."""
        revisions = pending_revisions("e2f3a4b5c6d7", PARTY_HEAD)

        assert EMAIL_CASE_CHECK in revisions


class TestOnlyPendingChecksAreReturned:
    def test_the_party_chain_declares_no_checks(self):
        """Eight migrations, not one precondition between them. This is the
        observation behind memship-context#80 and it is asserted so that
        writing one later is visible as a change in behaviour."""
        assert pending_checks(BASE_2_19, PARTY_HEAD) == []

    def test_the_email_check_is_returned_when_it_is_pending(self):
        revisions = [rev for rev, _ in pending_checks("e2f3a4b5c6d7", PARTY_HEAD)]

        assert revisions == [EMAIL_CASE_CHECK, EMAIL_WHITESPACE_CHECK]

    def test_an_unmigrated_database_has_nothing_to_check(self):
        """No alembic_version means an empty database: no data exists, so no
        data precondition can be violated, and every check would query tables
        that are not there yet. `upgrade.sh` skips the gate in this case
        anyway; this is the defensive half."""
        assert pending_checks(None, PARTY_HEAD) == []


class TestADowngradeHasNoPendingUpgrade:
    def test_a_target_behind_the_database_resolves_to_nothing(self):
        """`upgrade.sh --allow-downgrade` points an older release at a newer
        database, so the target is not an ancestor and alembic's walker
        refuses the range. No upgrade migration is pending, so there is nothing
        for a precondition to refuse.

        The exit code matters more than the list: an unhandled error here would
        leave the module exiting 1, which `upgrade.sh` reads as "a migration
        would refuse" rather than "the checks could not run".
        """
        assert pending_revisions(PARTY_HEAD, BASE_2_19) == []
