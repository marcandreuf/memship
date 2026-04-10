"""Payment provider configuration schemas.

Defines the expected config fields for each provider type.
Used by both backend validation and frontend form rendering.
"""

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
                "required": False,
            },
            {
                "key": "mode",
                "label": "Payment Mode",
                "type": "select",
                "options": ["webhook", "polling"],
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


def validate_provider_config(provider_type: str, config: dict) -> list[str]:
    """Validate a provider config dict against its schema.

    Returns a list of error messages (empty = valid).
    """
    schema = PROVIDER_CONFIG_SCHEMAS.get(provider_type)
    if not schema:
        return [f"Unknown provider type: {provider_type}"]

    errors = []
    for field_def in schema["fields"]:
        key = field_def["key"]
        required = field_def.get("required", False)
        value = config.get(key)

        if required and (value is None or value == ""):
            errors.append(f"Missing required field: {field_def['label']}")
            continue

        if value and field_def["type"] == "select":
            options = field_def.get("options", [])
            if options and value not in options:
                errors.append(
                    f"Invalid value for {field_def['label']}: "
                    f"must be one of {options}"
                )

    # Provider-specific format validation
    if not errors:
        errors.extend(_validate_format(provider_type, config))

    return errors


def _validate_format(provider_type: str, config: dict) -> list[str]:
    """Provider-specific format validation rules."""
    errors = []

    if provider_type == "stripe":
        sk = config.get("secret_key", "")
        pk = config.get("publishable_key", "")
        if sk and not sk.startswith("sk_"):
            errors.append("Secret Key must start with 'sk_'")
        if pk and not pk.startswith("pk_"):
            errors.append("Publishable Key must start with 'pk_'")

    elif provider_type == "redsys":
        mc = config.get("merchant_code", "")
        tid = config.get("terminal_id", "")
        cc = config.get("currency_code", "")
        if mc and not mc.isdigit():
            errors.append("Merchant Code must be numeric")
        if tid and not tid.isdigit():
            errors.append("Terminal ID must be numeric")
        if cc and (not cc.isdigit() or len(cc) != 3):
            errors.append("Currency Code must be a 3-digit ISO code")

    return errors
