/// <reference types="cypress" />

import { TEST_ACCOUNTS } from "../../support/commands";

// Assigning is `users.write`, which an ordinary admin holds — authoring is not.
// That split is the whole shape of the version: the super admin decides what a
// role can do, the admin decides who holds it.
describe("Roles — assignment", { tags: ["@roles"] }, () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/settings");
    cy.contains("button", "Accounts").click();
  });

  it("assigns a custom role to an account", { tags: ["@smoke"] }, () => {
    cy.get('[data-testid="user-search"]').type(TEST_ACCOUNTS.member.email);
    cy.get(`[data-testid="user-row-${TEST_ACCOUNTS.member.email}"]`)
      .contains("button", "Edit")
      .click();

    cy.get('[data-testid="assign-role-treasurer"]').find("button").click();
    cy.contains("button", "Save").click();

    cy.get(`[data-testid="user-row-${TEST_ACCOUNTS.member.email}"]`)
      .contains("Tesorero")
      .should("be.visible");
  });

  it("disables super_admin with a reason rather than hiding it", () => {
    cy.get('[data-testid="user-search"]').type(TEST_ACCOUNTS.member.email);
    cy.get(`[data-testid="user-row-${TEST_ACCOUNTS.member.email}"]`)
      .contains("button", "Edit")
      .click();

    // Present but unusable — an absent row reads as "no such role" and leaves
    // the admin wondering; the point is that it exists and is out of reach.
    cy.get('[data-testid="assign-role-super_admin"]')
      .should("exist")
      .within(() => {
        cy.get("button").should("be.disabled");
        cy.contains("Only a super admin can assign this role").should("exist");
      });
  });

  it("locks the member row, which no caller can remove", () => {
    cy.get('[data-testid="user-search"]').type(TEST_ACCOUNTS.member.email);
    cy.get(`[data-testid="user-row-${TEST_ACCOUNTS.member.email}"]`)
      .contains("button", "Edit")
      .click();

    cy.get('[data-testid="assign-role-member"]').within(() => {
      cy.get("button").should("be.disabled");
      cy.contains("Every account holds the Member role permanently").should("exist");
    });
  });

  it("restores the member account to its seeded roles", () => {
    cy.get('[data-testid="user-search"]').type(TEST_ACCOUNTS.member.email);
    cy.get(`[data-testid="user-row-${TEST_ACCOUNTS.member.email}"]`)
      .contains("button", "Edit")
      .click();
    cy.get('[data-testid="assign-role-treasurer"]').find("button").click();
    cy.contains("button", "Save").click();

    cy.get(`[data-testid="user-row-${TEST_ACCOUNTS.member.email}"]`)
      .contains("Tesorero")
      .should("not.exist");
  });

  it("deactivates and reactivates an account", () => {
    cy.get('[data-testid="user-search"]').type(TEST_ACCOUNTS.member.email);
    cy.get(`[data-testid="user-row-${TEST_ACCOUNTS.member.email}"]`)
      .find("button[role='switch']")
      .click();
    cy.get(`[data-testid="user-row-${TEST_ACCOUNTS.member.email}"]`)
      .find("button[role='switch']")
      .should("have.attr", "data-state", "unchecked");

    cy.get(`[data-testid="user-row-${TEST_ACCOUNTS.member.email}"]`)
      .find("button[role='switch']")
      .click();
    cy.get(`[data-testid="user-row-${TEST_ACCOUNTS.member.email}"]`)
      .find("button[role='switch']")
      .should("have.attr", "data-state", "checked");
  });

  it("offers no way to create an account", () => {
    // Accounts come from the registration form or SSO; the screen assigns
    // roles to accounts that already exist and nothing else.
    cy.contains("button", "Create").should("not.exist");
  });
});
