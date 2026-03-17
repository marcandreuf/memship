"""Unit tests for member service logic."""

import pytest

from app.domains.members.service import VALID_STATUS_TRANSITIONS


class TestStatusTransitions:
    def test_pending_can_go_active(self):
        assert "active" in VALID_STATUS_TRANSITIONS["pending"]

    def test_pending_can_go_cancelled(self):
        assert "cancelled" in VALID_STATUS_TRANSITIONS["pending"]

    def test_active_can_go_suspended(self):
        assert "suspended" in VALID_STATUS_TRANSITIONS["active"]

    def test_active_cannot_go_pending(self):
        assert "pending" not in VALID_STATUS_TRANSITIONS["active"]

    def test_cancelled_cannot_go_anywhere(self):
        assert VALID_STATUS_TRANSITIONS["cancelled"] == []

    def test_expired_can_go_active(self):
        assert "active" in VALID_STATUS_TRANSITIONS["expired"]

    def test_suspended_can_go_active(self):
        assert "active" in VALID_STATUS_TRANSITIONS["suspended"]
