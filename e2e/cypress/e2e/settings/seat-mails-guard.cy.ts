import { TEST_ACCOUNTS } from "../../support/commands";
import { API, cancelActivity, createPaidActivity } from "../../support/pay-to-confirm";

// Choosing which emails the club sends is the club admin's, not only the super
// admin's (#591), and the mails auto-cancel relies on cannot be switched off
// while it can release a seat.
//
// Global state: the three seat mails are switched on (a monotonic enabler, as
// every other spec that writes settings), and the refusal leaves them on. The
// activity with auto-cancel on is this spec's own and is cancelled afterwards,
// which is what stops it counting.

const SEAT_MAILS = ["registration_pending_payment", "payment_deadline_reminder", "registration_cancelled_unpaid"];

describe("Pay to confirm — the mails auto-cancel relies on", () => {
  let activityId: number | undefined;

  before(() => {
    cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
    cy.request("PUT", `${API}/settings/communications`, {
      templates: Object.fromEntries(SEAT_MAILS.map((key) => [key, true])),
    });
  });

  afterEach(() => {
    cancelActivity(activityId);
    activityId = undefined;
  });

  it("are on a tab the club admin can open", () => {
    cy.loginAsAdmin();
    cy.visit("/en/settings");
    cy.settingsTab("Members", "Communications");
    cy.get('[role="switch"][aria-label="Registration pending payment"]').should("be.visible");
  });

  it("cannot be switched off while an activity cancels unpaid seats", () => {
    createPaidActivity(`E2E Auto-cancel ${Date.now()}`, { autoCancel: true }).then((id) => {
      activityId = id;
    });

    cy.loginAsAdmin();
    cy.visit("/en/settings");
    cy.settingsTab("Members", "Communications");
    cy.get('[role="switch"][aria-label="Registration pending payment"]')
      .should("have.attr", "aria-checked", "true")
      .click();
    cy.get('[role="alertdialog"]').contains("button", "Switch off").click();
    // The emails card has its own Save, below it; the one above saves the
    // announcements switch.
    cy.get('[role="switch"][aria-label="Registration pending payment"]')
      .closest('[data-slot="card"]')
      .next("button")
      .should("have.text", "Save")
      .click();

    cy.contains("Automatic cancellation is on, so these emails cannot be switched off").should("be.visible");
    cy.request(`${API}/settings/communications`).then((r) => {
      const pending = r.body.templates.find((t: { key: string }) => t.key === "registration_pending_payment");
      expect(pending.enabled).to.eq(true);
    });
  });
});
