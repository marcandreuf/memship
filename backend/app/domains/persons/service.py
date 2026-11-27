"""Person service — writes that more than one domain has to get right.

``change_person_email`` lives here, below both of its callers, because the two
rows it keeps together belong to different domains: the address the organisation
mails is a party fact and the address someone signs in with is an auth fact.
Putting it in ``members`` is what let a second endpoint write one without the
other (#636).
"""

from sqlalchemy.orm import Session

from app.domains.auth.models import User
from app.domains.persons.models import Person


class EmailTaken(ValueError):
    """Another account already signs in with this address."""


def change_person_email(db: Session, person: Person, email: str | None) -> None:
    """Write a person's address to the party row and to their User row, if any.

    Login reads ``users.email`` while every mail the app sends reads the party's
    address through ``Person.email``, which is an association proxy onto
    ``Party.email``. Writing only the party row sends mail to the corrected
    address while sign-in still expects the old one, and nothing surfaces the
    split. The two rows are one address, so they move together.

    ``users.email`` is unique, so the address must not belong to another
    account. The party row is only checked against Users: a person with no login
    (an admin-created member) may share an address with one, as before, since a
    minor and a guardian legitimately do.

    This was #98, fixed in ``change_member_email`` and in the member update
    endpoint. ``PUT /persons/{id}`` assigned straight to the model and so had
    the same defect until #636; it is now the second caller of this function,
    which is why the function sits in ``persons`` rather than in ``members``.
    """
    user = person.user
    if user is not None:
        if not email:
            raise ValueError("A member with a login must keep an email address")
        taken = (
            db.query(User).filter(User.email == email, User.id != user.id).first()
        )
        if taken:
            raise EmailTaken("Email already registered")
        user.email = email
    person.email = email
