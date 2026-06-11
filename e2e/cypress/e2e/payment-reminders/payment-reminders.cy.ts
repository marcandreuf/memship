// =============================================================================
// Payment Reminders (v0.4.5) — Settings tab, manual send + history, RBAC
// =============================================================================

describe("Payment Reminders — Settings tab (super admin)", () => {
  beforeEach(() => {
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.contains('[role="tab"]', "Payment reminders").click();
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
    cy.contains('[role="tab"]', "Membership Types").click();
    cy.contains(/full member|student/i).should("be.visible");
  });
});

describe("Payment Reminders — receipt detail (admin)", () => {
  it("sends a manual reminder and records it in the history", () => {
    cy.loginAsAdmin();
    // Emitted receipts are remindable; the seed has several.
    cy.visit("/en/receipts?status=emitted");
    cy.get("table tbody tr").first().click();
    cy.url().should("match", /\/receipts\/\d+/);

    cy.contains("button", "Send reminder").click();
    cy.contains(/reminder sent/i).should("be.visible");

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
