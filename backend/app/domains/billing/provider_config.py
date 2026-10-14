"""Payment provider configuration schemas.

Defines the expected config fields for each provider type.
Used by both backend validation and frontend form rendering.
"""

# The provider types that have an adapter behind them. `PROVIDER_CONFIG_SCHEMAS`
# describes the *form* for a type; this says whether anything will process a
# payment once it is filled in. `goCardless` and `paypal` have a schema and no
# adapter, so a provider of either type could be created, tested and activated
# while being incapable of taking a payment — an administrator told a method was
# live that is not offered to any member (#340).
#
# Kept beside the schemas so the two cannot drift: adding a schema without an
# adapter is the mistake this guards.
AVAILABLE_PROVIDER_TYPES: frozenset[str] = frozenset(
    {"sepa_direct_debit", "stripe", "redsys"}
)


PROVIDER_CONFIG_SCHEMAS: dict[str, dict] = {
    "sepa_direct_debit": {
        "fields": [
            {
                "key": "format",
                "label": "SEPA Format",
                "type": "select",
                "options": ["pain.008.001.02"],
                "required": True,
            },
        ],
        "sensitive_fields": [],
    },
    "stripe": {
        "fields": [
            {
                "key": "secret_key",
                "label": "Secret Key",
                "type": "password",
                "placeholder": "sk_live_...",
                "required": True,
            },
            {
                "key": "publishable_key",
                "label": "Publishable Key",
                "type": "text",
                "placeholder": "pk_live_...",
                "required": True,
            },
            {
                "key": "webhook_secret",
                "label": "Webhook Secret",
                "type": "password",
                "placeholder": "whsec_...",
                "required": True,
            },
        ],
        "sensitive_fields": ["secret_key", "webhook_secret"],
    },
    "redsys": {
        "fields": [
            {
                "key": "merchant_code",
                "label": "Merchant Code (FUC)",
                "type": "text",
                "required": True,
            },
            {
                "key": "terminal_id",
                "label": "Terminal ID",
                "type": "text",
                "required": True,
            },
            {
                "key": "secret_key",
                "label": "Signing Key",
                "type": "password",
                "required": True,
            },
            {
                "key": "environment",
                "label": "Environment",
                "type": "select",
                "options": ["test", "production"],
                "required": True,
            },
            {
                "key": "currency_code",
                "label": "Currency Code",
                "type": "text",
                "placeholder": "978 (EUR)",
                "required": True,
            },
        ],
        "sensitive_fields": ["secret_key"],
    },
    "goCardless": {
        "fields": [
            {
                "key": "access_token",
                "label": "Access Token",
                "type": "password",
                "required": True,
            },
            {
                "key": "webhook_secret",
                "label": "Webhook Secret",
                "type": "password",
                "required": False,
            },
            {
                "key": "environment",
                "label": "Environment",
                "type": "select",
                "options": ["sandbox", "live"],
                "required": True,
            },
        ],
        "sensitive_fields": ["access_token", "webhook_secret"],
    },
    "paypal": {
        "fields": [
            {
                "key": "client_id",
                "label": "Client ID",
                "type": "text",
                "required": True,
            },
            {
                "key": "client_secret",
                "label": "Client Secret",
                "type": "password",
                "required": True,
            },
            {
                "key": "environment",
                "label": "Environment",
                "type": "select",
                "options": ["sandbox", "live"],
                "required": True,
            },
        ],
        "sensitive_fields": ["client_secret"],
    },
}


def get_sensitive_fields(provider_type: str) -> list[str]:
    """Return the list of sensitive fields for a provider type."""
    schema = PROVIDER_CONFIG_SCHEMAS.get(provider_type)
    if not schema:
        return []
    return schema.get("sensitive_fields", [])


def get_required_fields(provider_type: str) -> list[str]:
    """Return the list of required field keys for a provider type."""
    schema = PROVIDER_CONFIG_SCHEMAS.get(provider_type)
    if not schema:
        return []
    return [f["key"] for f in schema["fields"] if f.get("required")]


def validate_provider_config(provider_type: str, config: dict) -> list[dict]:
    """Validate a provider config dict against its schema.

    Returns a list of structured errors (empty = valid), not sentences: these
    reach an administrator's screen, and the organization may not be running in
    English (#223). Each carries a ``code`` and whatever the message needs to be
    built — the field key, never a rendered label, so the locale files own both
    halves of the sentence.
    """
    schema = PROVIDER_CONFIG_SCHEMAS.get(provider_type)
    if not schema:
        return [{"code": "unknown_provider_type", "provider_type": provider_type}]

    errors: list[dict] = []
    for field_def in schema["fields"]:
        key = field_def["key"]
        required = field_def.get("required", False)
        value = config.get(key)

        if required and (value is None or value == ""):
            errors.append({"code": "missing_required_field", "field": key})
            continue

        if value and field_def["type"] == "select":
            options = field_def.get("options", [])
            if options and value not in options:
                errors.append(
                    {"code": "invalid_option", "field": key, "options": options}
                )

    errors.extend(_validate_format(provider_type, config))

    return errors


def validate_provider_format(provider_type: str, config: dict) -> list[dict]:
    """The format rules alone, with no opinion about missing fields.

    A half-filled config is a normal thing to save: an administrator pastes the
    keys as they find them and switches the provider on afterwards, and
    activation is where `validate_provider_config` insists on the whole set. But
    a value that *is* present can be checked the moment it arrives, and a stored
    typo is worth refusing at the keystroke rather than at activation — or, for
    a signing secret, never, since nothing local can tell it is wrong.
    """
    if provider_type not in PROVIDER_CONFIG_SCHEMAS:
        return [{"code": "unknown_provider_type", "provider_type": provider_type}]
    return _validate_format(provider_type, config)


def _validate_format(provider_type: str, config: dict) -> list[dict]:
    """Provider-specific format validation rules."""
    errors: list[dict] = []

    if provider_type == "stripe":
        sk = config.get("secret_key", "")
        pk = config.get("publishable_key", "")
        if sk and not sk.startswith("sk_"):
            errors.append(
                {"code": "must_start_with", "field": "secret_key", "prefix": "sk_"}
            )
        if pk and not pk.startswith("pk_"):
            errors.append(
                {"code": "must_start_with", "field": "publishable_key", "prefix": "pk_"}
            )
        # Only Stripe knows whether a signing secret is the right one, so a
        # wrong-but-well-formed value still fails quietly at the webhook: every
        # confirmation is discarded, the member sees success and the receipt
        # stays unpaid. The prefix is the one part of it that can be checked
        # here, and it catches the paste that grabbed the wrong field.
        ws = config.get("webhook_secret", "")
        if ws and not ws.startswith("whsec_"):
            errors.append(
                {"code": "must_start_with", "field": "webhook_secret", "prefix": "whsec_"}
            )

    elif provider_type == "redsys":
        mc = config.get("merchant_code", "")
        tid = config.get("terminal_id", "")
        cc = config.get("currency_code", "")
        if mc and not mc.isdigit():
            errors.append({"code": "must_be_numeric", "field": "merchant_code"})
        if tid and not tid.isdigit():
            errors.append({"code": "must_be_numeric", "field": "terminal_id"})
        if cc and (not cc.isdigit() or len(cc) != 3):
            errors.append(
                {"code": "must_be_digits", "field": "currency_code", "length": 3}
            )

    return errors
