// =============================================================================
// Membership lapse — settings tab: the controls, the unwarned-cutoff warning
// =============================================================================

describe("Membership lapse — Settings tab (super admin)", () => {
  beforeEach(() => {
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.settingsTab("Payments", "Membership lapse");
  });

  it("shows the reversion controls", () => {
    cy.contains("Revert unpaid members to the free tier").should("be.visible");
    cy.contains("Payment term (days)").should("be.visible");
    cy.contains("Grace period (days)").should("be.visible");
    cy.contains("button", "Save").should("be.visible");
  });

  it("warns that reversion without reminders cuts members off unwarned", () => {
    // The warning is the point of the tab: reversion runs whether or not
    // dunning is on, so a club can downgrade members it never chased.
    cy.get('[role="switch"]').then(($sw) => {
      if ($sw.attr("aria-checked") !== "true") {
        cy.wrap($sw).click();
      }
    });

    cy.settingsTab("Payments", "Payment reminders");
    cy.get('[role="switch"]')
      .invoke("attr", "aria-checked")
      .then((remindersOn) => {
        cy.settingsTab("Payments", "Membership lapse");
        if (remindersOn === "true") {
          cy.contains("Payment reminders are switched off").should("not.exist");
        } else {
          cy.contains("Payment reminders are switched off").should("be.visible");
        }
      });
  });

  it("enables reversion, sets the windows, and saves", () => {
    cy.get('[role="switch"]').then(($sw) => {
      if ($sw.attr("aria-checked") !== "true") {
        cy.wrap($sw).click();
      }
    });
    cy.get('[role="switch"]').should("have.attr", "aria-checked", "true");

    cy.get('input[name="membership_fee_due_days"]').clear().type("7");
    cy.get('input[name="membership_lapse_grace_days"]').clear().type("21");
    cy.contains("button", "Save").click();

    cy.contains(/saved successfully/i).should("be.visible");
    cy.contains("about 28 days").should("be.visible");
  });

  it("does not clobber other feature flags (membership types still load)", () => {
    // Saving the lapse keys must merge into the features JSONB, not replace it.
    cy.settingsTab("Members", "Membership Types");
    cy.contains(/full member|student/i).should("be.visible");
  });
});
