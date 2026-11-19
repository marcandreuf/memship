"""Money rounding — one quantisation rule for every euro amount the app computes.

Every derived amount (VAT, a percentage discount, a prorated first period) is
rounded here and nowhere else. Two rules were in use before this module existed:
billing quantised with an explicit ``ROUND_HALF_UP`` while ``discount_service``
called a bare ``.quantize(Decimal("0.01"))``, which silently inherits whatever
rounding the ambient decimal context carries — ``ROUND_HALF_EVEN`` by default.
The two disagree by a cent on an exact half, so a discounted registration could
contradict the receipt raised from it, and nothing in the source said so.

``ROUND_HALF_UP`` is the rule that wins: it is the ordinary convention for VAT
in Spain and it is what the billing paths already applied.

This does not cover the two places that convert a euro amount to minor units for
a payment provider (``sepa_xml`` and ``stripe_provider``). Those truncate rather
than round, which is a different defect, tracked separately.
"""

from decimal import ROUND_HALF_UP, Decimal

from babel.numbers import format_currency
from jinja2 import pass_context

# Euro cents: the only precision a stored or transmitted amount ever has.
CENTS = Decimal("0.01")


def round_money(amount: Decimal) -> Decimal:
    """Round ``amount`` to two decimals, half away from zero.

    Always pass a ``Decimal``. A float has already lost the exact half this
    function exists to decide.
    """
    return amount.quantize(CENTS, rounding=ROUND_HALF_UP)


def format_money(amount: Decimal | str | float, currency: str, locale: str) -> str:
    """``amount`` as the reader of ``locale`` writes it: 36,30 € in es and ca,
    €36.30 in en (#607). The single place amounts become text for a person.

    Always two decimals, whatever the currency: every stored amount has cents,
    and a currency's own digits (none for JPY) would show 1234.50 as 1.234 —
    a figure that is not the one on the receipt."""
    return format_currency(
        Decimal(str(amount)),
        currency or "EUR",
        locale=locale if locale in ("es", "ca", "en") else "es",
        currency_digits=False,
    )


@pass_context
def money_filter(context, amount, currency: str) -> str:
    """Jinja ``money`` filter: ``{{ amount | money(currency) }}``, in the locale
    the template is rendered in. Email and PDF templates both receive ``locale``."""
    if amount is None or amount == "":
        return ""
    return format_money(amount, currency, context.get("locale", "es"))
