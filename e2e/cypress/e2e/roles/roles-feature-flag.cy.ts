/// <reference types="cypress" />

// `features.custom_roles` gates the screens and their API, never the permission
// layer — authorization keeps working with the flag off, only this surface
// disappears. The Roles tab itself survives because it carries the switch.
describe("Roles — feature flag", { tags: ["@roles"] }, () => {
  beforeEach(() => {
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.contains("button", "Roles").click();
  });

  afterEach(() => {
    // Leave the seed as we found it — every other roles spec needs it on.
    // Re-enter the tab: a test may have navigated away from settings.
    cy.visit("/en/settings");
    cy.contains("button", "Roles").click();
    cy.get('[data-testid="custom-roles-toggle"]').then(($toggle) => {
      if ($toggle.attr("data-state") === "unchecked") cy.wrap($toggle).click();
    });
  });

  it("hides the roles list and the Accounts tab when off", () => {
    cy.get('[data-testid="custom-roles-toggle"]').click();

    cy.get('[data-testid="role-row-admin"]').should("not.exist");
    cy.contains("button", "Create role").should("not.exist");
    cy.contains("button", "Accounts").should("not.exist");
  });

  it("leaves the rest of the app alone", () => {
    cy.get('[data-testid="custom-roles-toggle"]').click();

    cy.visit("/en/members");
    cy.get("table tbody tr").should("have.length.greaterThan", 0);
    cy.visit("/en/receipts");
    cy.get("table tbody tr").should("have.length.greaterThan", 0);
  });

  it("brings both tabs back when on", () => {
    cy.get('[data-testid="custom-roles-toggle"]').click();
    cy.get('[data-testid="custom-roles-toggle"]').click();

    cy.get('[data-testid="role-row-admin"]').should("exist");
    cy.contains("button", "Accounts").should("be.visible");
  });
});
