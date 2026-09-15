"""#187: `members.user_id` holds no unique constraint, so a user who cancelled
and rejoined on a fresh row can resolve to either one. `current_member_or_403`
must pick the live, most recent row deterministically rather than whatever
order Postgres happens to return.
"""

from fastapi import HTTPException

from app.core.db_utils import current_member_or_403
from app.domains.auth.models import User
from app.domains.members.models import Member
from app.domains.persons.models import Person


def _user(db, email):
    person = Person(first_name="Lookup", last_name="Tester", email=email)
    db.add(person)
    db.flush()
    user = User(person_id=person.id, email=email, password_hash="x", role="member", is_active=True)
    db.add(user)
    db.flush()
    return user


def _member(db, user, person, *, is_active):
    member = Member(person_id=person.id, user_id=user.id, is_active=is_active)
    db.add(member)
    db.flush()
    return member


class TestDuplicateMemberRows:
    def test_the_active_row_wins_over_a_cancelled_one_created_first(self, db):
        user = _user(db, "dup-active-second@examplee6e3b1.com")
        cancelled = _member(db, user, user.person, is_active=False)
        active = _member(db, user, user.person, is_active=True)
        assert cancelled.id < active.id

        resolved = current_member_or_403(db, user)

        assert resolved.id == active.id

    def test_the_active_row_wins_even_when_it_is_the_older_row(self, db):
        user = _user(db, "dup-active-first@examplee6e3b1.com")
        active = _member(db, user, user.person, is_active=True)
        cancelled = _member(db, user, user.person, is_active=False)
        assert active.id < cancelled.id

        resolved = current_member_or_403(db, user)

        assert resolved.id == active.id

    def test_two_cancelled_rows_resolve_to_the_most_recent(self, db):
        user = _user(db, "dup-both-cancelled@examplee6e3b1.com")
        older = _member(db, user, user.person, is_active=False)
        newer = _member(db, user, user.person, is_active=False)
        assert older.id < newer.id

        resolved = current_member_or_403(db, user)

        assert resolved.id == newer.id

    def test_active_only_still_refuses_when_only_a_cancelled_row_exists(self, db):
        user = _user(db, "dup-active-only@examplee6e3b1.com")
        _member(db, user, user.person, is_active=False)

        try:
            current_member_or_403(db, user, active_only=True)
            assert False, "expected a 403"
        except HTTPException as exc:
            assert exc.status_code == 403
            assert exc.detail["code"] == "not_a_member"
