"""Unit tests for remittance service — status transitions."""

import pytest

from app.domains.billing.remittance_service import validate_remittance_transition


class TestRemittanceTransitions:
    def test_draft_to_ready(self):
        validate_remittance_transition("draft", "ready")

    def test_draft_to_cancelled(self):
        validate_remittance_transition("draft", "cancelled")

    def test_ready_to_submitted(self):
        validate_remittance_transition("ready", "submitted")

    def test_ready_to_cancelled(self):
        validate_remittance_transition("ready", "cancelled")

    def test_submitted_to_processed(self):
        validate_remittance_transition("submitted", "processed")

    def test_processed_to_closed(self):
        validate_remittance_transition("processed", "closed")

    def test_closed_is_terminal(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            validate_remittance_transition("closed", "cancelled")

    def test_cancelled_is_terminal(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            validate_remittance_transition("cancelled", "draft")

    def test_draft_cannot_skip_to_submitted(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            validate_remittance_transition("draft", "submitted")

    def test_submitted_cannot_go_back(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            validate_remittance_transition("submitted", "ready")
