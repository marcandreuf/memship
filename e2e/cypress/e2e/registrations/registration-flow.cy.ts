describe("Registration Flow", () => {
  it("member can browse published activities @smoke", () => {
    cy.loginAsMember();
    cy.visit("/en/activities");
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
