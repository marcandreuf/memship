"""Stripe customer sync — lazy creation of Stripe customers from persons."""

import logging

import stripe
from sqlalchemy.orm import Session

from app.domains.persons.models import Person

logger = logging.getLogger(__name__)


def ensure_customer(
    db: Session, person: Person, stripe_secret_key: str
) -> str:
    """Return a Stripe customer ID for this person, creating one if needed.

    Lazy-creates on first payment. Stores stripe_customer_id on the person
    so subsequent calls skip the API.
    """
    if person.stripe_customer_id:
        return person.stripe_customer_id

    client = stripe.StripeClient(stripe_secret_key)
    customer = client.customers.create(
        params={
            "email": person.email,
            "name": f"{person.first_name} {person.last_name}",
            "metadata": {"person_id": str(person.id)},
        }
    )

    person.stripe_customer_id = customer.id
    db.flush()

    logger.info("Created Stripe customer %s for person %s", customer.id, person.id)
    return customer.id
