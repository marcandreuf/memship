"""The canonical set of keys ``organization_settings.features`` accepts.

``features`` is free-form JSONB and the settings update merges sparsely, so
before this existed any key a request carried was written and then kept
forever: a typo in a flag name answered 200, configured nothing, and left no
record of why (#494). Nothing checked the name because no list of the names
existed anywhere in the code; the nearest thing was ``DEMO_FEATURES`` in
``cli/demo_data.py``, a demo seed naming nineteen of the twenty-one.

The set is assembled from each domain's own declaration rather than restated
here, so a domain that adds a configuration value registers it in one place and
cannot register it twice. Only the gates are declared here, because the domains
enforcing them have no ``rules.py``: each is a single read, not a set of tuned
values.

The four groups mirror the specification's four classes, which is why they are
separate constants rather than one flat set. **Adding a flag to the product
means adding it here**, and ``TestTheCanonicalSetIsPinned`` is what makes that
a failing test rather than a silent 422 the first time an admin saves it.

Not in scope: ``activities.features``, a different JSONB column on a different
table, which carries ``waiting_list`` per activity. The name collision is a
trap for anyone grepping ``features.get(`` across the backend.
"""

from app.domains.billing.rules import FEATURE_KEYS as BILLING_FEATURE_KEYS
from app.domains.bookings.rules import FEATURE_KEYS as BOOKING_FEATURE_KEYS

#: Whether a module exists on this instance at all. Enforced in the endpoint
#: and answering 404, so an absent feature does not disclose that it exists
#: (#304).
MODULE_GATE_KEYS = frozenset(
    {
        "bookings",
        "communications",
        "custom_profile_fields",
        "custom_roles",
        "member_card",
    }
)

#: Refuses one action on an endpoint every instance has, and so answers 403
#: rather than 404: ``POST /auth/register`` is a route on every install, and a
#: 404 there would be false and indistinguishable from a mistyped URL.
ACTION_GATE_KEYS = frozenset({"public_registration"})

#: Neither gate nor tuning value: the closed set of values the organization
#: offers, enforced against submissions by ``require_offered_gender``.
OFFERED_VALUE_KEYS = frozenset({"gender_options"})

#: Changes what an action does rather than refusing it, so it belongs to no
#: gate class: off means a self-registration is approved inline instead of
#: landing ``pending``.
POLICY_KEYS = frozenset({"registration_requires_approval"})

FEATURE_KEYS = (
    MODULE_GATE_KEYS
    | ACTION_GATE_KEYS
    | OFFERED_VALUE_KEYS
    | POLICY_KEYS
    | BILLING_FEATURE_KEYS
    | BOOKING_FEATURE_KEYS
)
