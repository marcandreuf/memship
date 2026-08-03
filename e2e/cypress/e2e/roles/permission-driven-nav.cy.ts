/// <reference types="cypress" />

// The one place the whole chain runs as a single thing: catalog → role →
// assignment → per-request resolution (no role claim in the JWT) → /auth/me →
// has(key) → rendered sidebar. treasurer@test.com holds `billing.*` and the
// pinned `member` role, and nothing else.
describe("Permission-driven nav", { tags: ["@roles"] }, () => {
  beforeEach(() => {
    cy.loginAsTreasurer();
  });

  it("shows exactly the billing nav", { tags: ["@smoke"] }, () => {
    cy.get('[data-slot="sidebar"]').within(() => {
      cy.contains("Receipts").should("be.visible");
      cy.contains("Mandates").should("be.visible");
      cy.contains("Remittances").should("be.visible");
      cy.contains("Recurring billing").should("be.visible");
    });
  });

  it("withholds the nav its permissions do not cover", () => {
    cy.get('[data-slot="sidebar"]').within(() => {
      cy.contains("Members").should("not.exist");
      cy.contains("Groups").should("not.exist");
      cy.contains("Activities").should("not.exist");
      // No settings.read / membership.write / roles.read / users.read.
      cy.contains("Settings").should("not.exist");
      // reports.read is a separate key: aggregates are their own grant.
      cy.contains("Annual Summary").should("not.exist");
    });
  });

  it("renders only the dashboard cards its permissions cover", () => {
    cy.visit("/en/dashboard");
    cy.contains("Receipts").should("be.visible");
    cy.get("main").within(() => {
      cy.contains("Members").should("not.exist");
      cy.contains("Registrations").should("not.exist");
    });
  });

  it("returns no member data on a direct visit to a withheld route", () => {
    // The guard is server-side: `members.read` is missing, so the list 403s and
    // the page has nothing to render. Nav hiding is convenience, not the check.
    cy.visit("/en/members");
    cy.get("table tbody tr").should("not.exist");
  });

  it("still reaches its own member-side pages, because `member` is pinned", () => {
    // Staff are members too — every account holds the self-service keys.
    cy.visit("/en/profile");
    cy.contains("treasurer@test.com").should("be.visible");
  });
});

describe("Permission-driven nav — full admin", { tags: ["@roles"] }, () => {
  it("still sees everything it saw before v1.4", () => {
    cy.loginAsAdmin();
    cy.get('[data-slot="sidebar"]').within(() => {
      cy.contains("Members").should("be.visible");
      cy.contains("Activities").should("be.visible");
      cy.contains("Receipts").should("be.visible");
      cy.contains("Settings").should("be.visible");
    });
  });
});
