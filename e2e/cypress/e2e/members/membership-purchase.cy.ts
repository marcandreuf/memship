// Buying a membership plan from the member portal.
//
// The assertions avoid naming the free tier the seeded member happens to hold —
// which tier carries `is_default` differs between a freshly migrated database
// and one seeded more than once. What matters is that it is free, so the
// catalogue must not try to sell it back to them.
//
// The purchase test is last on purpose: it leaves an unpaid receipt behind, and
// the awaiting-payment panel is then visible on later runs. That is not a
// leaked fixture — a second purchase voids the first, so the flow is the same
// every time — but the assertions above it must not depend on the panel being
// absent.

describe("Membership purchase", () => {
  beforeEach(() => {
    cy.loginAsMember();
    cy.visit("/en/my-membership");
    // The catalogue and the receipt list resolve independently, and the page
    // re-renders when the slower one lands. Waiting for both here keeps a
    // later click from being aimed at an element about to be replaced.
    cy.get('[data-testid="plan-catalogue"]').should("be.visible");
    cy.get('[data-testid="current-plan"]').should("be.visible");
  });

  it("is reachable from the sidebar", () => {
    cy.visit("/en/dashboard");
    cy.contains("a", /my plan/i).click();
    cy.url().should("include", "/my-membership");
  });

  it("names the plan the member currently holds", () => {
    cy.get('[data-testid="current-plan"]')
      .should("contain.text", "Current plan")
      .invoke("text")
      .should("match", /Current plan\s*\S/);
  });

  it("offers the paid plans", () => {
    cy.get('[data-testid="plan-catalogue"]').within(() => {
      cy.contains("Full Member").should("be.visible");
      cy.contains("Student").should("be.visible");
      // Amounts render through the org's locale and currency settings, so the
      // symbol and its position are the club's choice — only the figure is ours.
      cy.contains(/50[.,]00/).should("exist");
    });
  });

  it("does not offer a free plan or the one already held", () => {
    // Every free tier is granted by an admin, never sold: selling one would
    // raise a zero receipt that can never be paid, so the plan would never
    // activate. Honorary and Registered are the two the seed creates at 0.
    cy.get('[data-testid="plan-card-honorary"]').should("not.exist");
    cy.get('[data-testid="plan-card-registered"]').should("not.exist");
  });

  it("quotes the plan on the server before asking for confirmation", () => {
    cy.get('[data-testid="plan-card-full-member"]')
      .contains("button", /choose/i)
      .click();

    cy.get('[role="dialog"]').within(() => {
      cy.contains(/net amount/i).should("be.visible");
      cy.contains(/vat/i).should("be.visible");
      cy.contains(/total to pay now/i).should("be.visible");
      // The wart the issue insists is stated: buying is not having.
      cy.contains(/activates once the receipt is paid/i).should("be.visible");
    });
  });

  it("warns that a mid-period first charge is smaller than the plan price", () => {
    // The annual plan covers the rest of the calendar year in whole months
    // including the month of purchase, so it is prorated in every month but
    // January — when 12 of 12 are charged and there is nothing to warn about.
    // Deriving the expectation from today's date exercises the banner all year
    // instead of failing every January.
    const monthsCharged = 12 - new Date().getMonth();

    cy.get('[data-testid="plan-card-annual-member"]')
      .contains("button", /choose/i)
      .click();

    cy.get('[role="dialog"]').within(() => {
      if (monthsCharged === 12) {
        cy.contains(/of 12 months/i).should("not.exist");
        return;
      }
      cy.contains(`covers ${monthsCharged} of 12 months`).should("be.visible");
      cy.contains(/less than the plan price/i).should("be.visible");
      // The full fee that lands at the next boundary. Amounts render through
      // the org's locale and currency settings, so only the figure is ours.
      cy.contains(/200[.,]00/).should("be.visible");
    });
  });

  it("raises a receipt and leaves the member on their current plan", () => {
    cy.get('[data-testid="current-plan"]')
      .invoke("text")
      .then((before) => {
        cy.get('[data-testid="plan-card-student"]')
          .contains("button", /choose/i)
          .click();

        cy.get('[role="dialog"]')
          .contains("button", /buy and raise receipt/i)
          .click();

        cy.get('[role="dialog"]').should("not.exist");
        cy.get('[data-testid="pending-purchase"]')
          .should("be.visible")
          .and("contain.text", "Student")
          .and("contain.text", "Awaiting payment");

        // Unpaid grants nothing.
        cy.get('[data-testid="current-plan"]').should("have.text", before);
      });

    cy.visit("/en/my-receipts");
    cy.contains("Student").should("be.visible");
  });
});
