// =============================================================================
// Payment Reminders (v0.4.5) — Settings tab, manual send + history, RBAC
// =============================================================================

describe("Payment Reminders — Settings tab (super admin)", () => {
  beforeEach(() => {
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.settingsTab("Payments", "Payment reminders");
  });

  it("shows the payment reminder controls", () => {
    cy.contains("Enable payment reminders").should("be.visible");
    cy.contains("Days after due date").should("be.visible");
    cy.contains("Repeat every").should("be.visible");
    cy.contains("Maximum reminders").should("be.visible");
    cy.contains("button", "Save").should("be.visible");
  });

  it("enables reminders, sets the schedule, and saves", () => {
    cy.get('[role="switch"]').then(($sw) => {
      if ($sw.attr("aria-checked") !== "true") {
        cy.wrap($sw).click();
      }
    });
    cy.get('[role="switch"]').should("have.attr", "aria-checked", "true");

    cy.get('input[type="number"]').eq(0).clear().type("3");
    cy.get('input[type="number"]').eq(1).clear().type("7");
    cy.get('input[type="number"]').eq(2).clear().type("3");
    cy.contains("button", "Save").click();

    cy.contains(/saved successfully/i).should("be.visible");
  });

  it("does not clobber other feature flags (membership types still load)", () => {
    // Saving the reminder keys must merge into the features JSONB, not replace it.
    cy.settingsTab("Members", "Membership Types");
    cy.contains(/full member|student/i).should("be.visible");
  });
});

describe("Payment Reminders — receipt detail (admin)", () => {
  const API_URL = Cypress.env("API_URL") || "http://localhost:8003/api/v1";

  before(() => {
    // Outbound templates resolve DB-with-default and the default is off, so on
    // a freshly seeded instance `payment_reminder` does not send and the
    // endpoint refuses with 409 (#302). The default-off policy is deliberate,
    // so the spec configures the instance the way an administrator would.
    // This endpoint is a sparse update — it touches no sibling template.
    cy.apiLogin("super@examplee6e3b1.com", "TestSuper1!");
    cy.request({
      method: "PUT",
      url: `${API_URL}/settings/communications`,
      body: { templates: { payment_reminder: true } },
    })
      .its("status")
      .should("eq", 200);
  });

  it("sends a manual reminder and records it in the history", () => {
    cy.loginAsAdmin();
    // Ask for a receipt that is actually remindable rather than taking whatever
    // sorts first. "Emitted" is not enough: `canRemind` is
    // `!isCreditNote && status in (emitted, overdue)`
    // (`receipts/[id]/page.tsx:201`), and a credit note is emitted like any
    // other document. credit-note-lifecycle.cy.ts leaves one in the shared
    // database, it sorted first here on 2026-11-11, and the spec failed on a
    // page that correctly has no Send reminder button: you do not chase a
    // refund. Nothing about the ordering was wrong, the assumption was.
    cy.request({
      url: `${API_URL}/receipts?status=emitted&document_type=invoice&per_page=1`,
    }).then((resp) => {
      const receipt = resp.body.items[0];
      expect(receipt, "an emitted invoice to remind").to.exist;
      cy.visit(`/en/receipts/${receipt.id}`);
    });
    cy.url().should("match", /\/receipts\/\d+/);

    cy.contains("button", "Send reminder").click();
    cy.contains(/reminder queued/i).should("be.visible");

    // The history card appears with at least one reminder row.
    cy.get('[data-cy="reminder-history"]').should("be.visible");
    cy.get('[data-cy="reminder-history"] table tbody tr').should(
      "have.length.greaterThan",
      0
    );
  });
});

describe("Payment Reminders — Access control", () => {
  it("redirects members away from the admin receipts area", () => {
    cy.loginAsMember();
    cy.visit("/en/receipts");
    cy.url().should("include", "/dashboard");
  });
});
