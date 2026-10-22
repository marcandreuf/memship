"""Root test configuration.

Database fixtures are in tests/integration/conftest.py so that
unit tests can run without a database connection.
"""

import pytest


@pytest.fixture(autouse=True)
def _no_mail_health_writes(monkeypatch):
    """Keep sends from recording transport health on a session of their own.

    That write commits outside the test's transaction, so it would leak rows
    into every later test — or wait on a row the test itself holds. Tests of
    the recorder call it directly.
    """
    import app.core.email as email_module

    monkeypatch.setattr(email_module, "_record_send_outcome", lambda *args, **kwargs: None)
