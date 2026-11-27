describe("Registration Flow", () => {
  it("member can browse published activities @smoke", () => {
    cy.loginAsMember();
    // By name, not the first page as it falls: the list shows 20, newest first,
    // and the seeded Summer Soccer Camp is the 20th, so any activity another
    // worker publishes meanwhile pushes it to page 2 and this passes only on
    // retry. Same fix eligibility-rules 8.2 already carries (#461).
    cy.visit("/en/activities?q=Summer+Soccer+Camp");
    // Member sees activity cards (not table)
    cy.contains("Summer Soccer Camp").should("be.visible");
  });

  it("member sees My Activities page", () => {
    cy.loginAsMember();
    cy.visit("/en/my-activities");
    cy.contains(/my activities/i).should("be.visible");
  });

  it("member sees registrations in My Activities", () => {
    cy.loginAsMember();
    cy.visit("/en/my-activities");
    // Member should have seeded registrations (shown as cards)
    cy.contains(/confirmed/i).should("be.visible");
  });
});

describe("Registration — Admin View", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/activities");
    cy.get('input[placeholder*="Search"]').type("Soccer");
    cy.contains("Summer Soccer Camp").click();
    cy.url().should("match", /\/activities\/\d+/);
    cy.contains("button", "Registrations").click();
  });

  it("admin sees registrations table", () => {
    cy.get("table").should("be.visible");
    cy.get("table tbody tr").should("have.length.greaterThan", 0);
  });

  it("admin sees registration status badges", () => {
    cy.contains(/confirmed/i).should("be.visible");
  });

  it("admin sees status change controls", () => {
    cy.contains(/change statu/i).should("be.visible");
  });
});
