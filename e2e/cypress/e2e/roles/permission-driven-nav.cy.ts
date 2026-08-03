/// <reference types="cypress" />

// The one place the whole chain runs as a single thing: catalog → role →
// assignment → per-request resolution (no role claim in the JWT) → /auth/me →
// has(key) → rendered sidebar. treasurer@test.com holds `billing.*` and the
// pinned `member` role, and nothing else.
//
// Assertions go through hrefs rather than labels: "Receipts" is a substring of
// "My Receipts", and telling the staff item from the personal one is the whole
// point of these tests.
const navLink = (path: string) => `[data-slot="sidebar"] a[href="/en${path}"]`;

describe("Permission-driven nav", { tags: ["@roles"] }, () => {
  beforeEach(() => {
    cy.loginAsTreasurer();
  });

  it("shows exactly the billing nav", { tags: ["@smoke"] }, () => {
    cy.get(navLink("/receipts")).should("exist");
    cy.get(navLink("/mandates")).should("exist");
    cy.get(navLink("/remittances")).should("exist");
    cy.get(navLink("/billing-runs")).should("exist");
  });

  it("withholds the staff nav its permissions do not cover", () => {
    cy.get(navLink("/members")).should("not.exist");
    cy.get(navLink("/groups")).should("not.exist");
    // No settings.read / membership.write / roles.read / users.read.
    cy.get(navLink("/settings")).should("not.exist");
    // reports.read is a separate key: aggregates are their own grant.
    cy.get(navLink("/annual-summary")).should("not.exist");
  });

  it("keeps its personal nav, because `member` is pinned", () => {
    // The regression this guards: one administrative permission used to flip
    // the sidebar to the staff shape wholesale and take the self-service items
    // with it, even though the account still held every `self.*` key.
    cy.get(navLink("/my-receipts")).should("exist");
    cy.get(navLink("/my-activities")).should("exist");
    // The member-facing catalog, reached on self.activities.read.
    cy.get(navLink("/activities")).should("exist");
  });

  it("renders only the dashboard cards its permissions cover", () => {
    cy.visit("/en/dashboard");
    cy.get("main").within(() => {
      cy.contains("Registrations").should("not.exist");
    });
  });

  it("returns no member data on a direct visit to a withheld route", () => {
    // The guard is server-side: `members.read` is missing, so the list 403s and
    // the page has nothing to render. Nav hiding is convenience, not the check.
    cy.visit("/en/members");
    cy.get("table tbody tr").should("not.exist");
  });

  it("still reaches its own profile", () => {
    cy.visit("/en/profile");
    cy.contains("treasurer@test.com").should("be.visible");
  });

  it("gets the member catalog on /activities, not the staff list", () => {
    // The regression: the page picked its shape from "is this account staff at
    // all", so one unrelated administrative key turned the member catalog into
    // the admin list — complete with a Create button that 403s on save.
    cy.visit("/en/activities");
    cy.contains("New Activity").should("not.exist");
    cy.get("table").should("not.exist");
  });

  it("is redirected away from a route it cannot open", () => {
    cy.visit("/en/groups");
    cy.url().should("include", "/dashboard");
  });
});

describe("Permission-driven nav — full admin", { tags: ["@roles"] }, () => {
  beforeEach(() => {
    cy.loginAsAdmin();
  });

  it("still sees everything it saw before v1.4", () => {
    cy.get(navLink("/members")).should("exist");
    cy.get(navLink("/activities")).should("exist");
    cy.get(navLink("/receipts")).should("exist");
    cy.get(navLink("/settings")).should("exist");
  });

  it("sees the staff catalog once, not twice", () => {
    // `/activities` is offered by both the staff group and the personal one;
    // the staff entry wins and the duplicate is dropped.
    cy.get(navLink("/activities")).should("have.length", 1);
  });

  it("also has its own member surface — staff are members too", () => {
    cy.get(navLink("/my-receipts")).should("exist");
  });
});

describe("Permission-driven nav — plain member", { tags: ["@roles"] }, () => {
  it("sees the personal nav and none of the staff nav", () => {
    cy.loginAsMember();
    cy.get(navLink("/activities")).should("exist");
    cy.get(navLink("/my-receipts")).should("exist");
    cy.get(navLink("/members")).should("not.exist");
    cy.get(navLink("/receipts")).should("not.exist");
    cy.get(navLink("/settings")).should("not.exist");
  });
});