import { cancelActivity, createPaidActivity } from "../../support/pay-to-confirm";

// The organiser's side of setting up a paid activity (#591): the refusals come
// back translated, an unavailable payment method says what it needs, and the
// form says what switching auto-cancel on does to seats already held.

const REASONS: Record<string, string> = {
  Card: "Needs Stripe or Redsys active",
  Bizum: "Needs Redsys with Bizum enabled",
  "Bank transfer": "Needs the club's IBAN",
};

describe("Pay to confirm — activity form", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
  });

  it("refuses to publish a paid activity without payment methods, in words", () => {
    createPaidActivity(`E2E No Methods ${Date.now()}`, { paymentMethods: [], publish: false }).then((id) => {
      cy.loginAsAdmin();
      cy.visit(`/en/activities/${id}`);
      cy.contains("button", /^Publish$/).click();
      cy.get('[role="alertdialog"]').contains("button", /^Publish$/).click();
      cy.contains("A paid activity must accept at least one payment method to be published.").should(
        "be.visible"
      );
      cancelActivity(id);
    });
  });

  it("offers the waiting list and explains auto-cancel on a new activity", () => {
    cy.visit("/en/activities/new");
    cy.contains("label", "Waiting list").should("be.visible");

    cy.contains("label", "Cancel automatically if not paid")
      .parent()
      .find('[role="combobox"]')
      .click();
    cy.contains('[role="option"]', "On for this activity").click();
    cy.contains("Pending seats that have no deadline yet get the full time").should("be.visible");
  });

  it("says what an unavailable payment method needs", () => {
    cy.visit("/en/activities/new");
    // Every method is disabled until the options arrive. Cash needs nothing, so
    // it enabling is the sign the options have rendered.
    cy.contains("label", /^Cash/).find('button[role="checkbox"]').should("be.enabled");
    // Which methods are unavailable depends on the club's providers; whichever
    // are must give their own reason, and an admin is told to ask, not sent to
    // a settings tab only the super admin has.
    Object.entries(REASONS).forEach(([method, reason]) => {
      cy.contains("label", new RegExp(`^${method}`)).then(($label) => {
        if ($label.find('button[role="checkbox"]').is(":disabled")) {
          cy.wrap($label).should("contain", reason).and("contain", "ask an administrator");
        }
      });
    });
  });
});
