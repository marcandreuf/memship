/// <reference types="cypress" />

// An operator account administers the instance without belonging to the club
// (#168): `super@` and `admin@` are seeded with their staff role and no member
// record at all.
//
// The two halves pull against each other, and the second is the one that would
// be quietly lost. The member surface has to disappear — but it cannot be hidden
// by withholding `self.*`, because those keys are the floor on every route staff
// and members share (`/members/{id}`, the receipt PDFs). A staff role holds all
// of them and must keep holding them. What the nav hangs off is the member
// record, which an operator does not have.
const navLink = (path: string) => `[data-slot="sidebar"] a[href="/en${path}"]`;

describe("An operator account is not a club member", { tags: ["@roles"] }, () => {
  beforeEach(() => {
    cy.loginAsSuperAdmin();
  });

  it("lands on the dashboard and renders it", { tags: ["@smoke"] }, () => {
    cy.url().should("include", "/dashboard");
    cy.get("main").should("be.visible");
  });

  it("has none of the member nav", () => {
    cy.get(navLink("/my-activities")).should("not.exist");
    cy.get(navLink("/my-bookings")).should("not.exist");
    cy.get(navLink("/my-membership")).should("not.exist");
    cy.get(navLink("/my-receipts")).should("not.exist");
    cy.get(navLink("/my-card")).should("not.exist");
  });

  it("keeps the staff nav it administers with", () => {
    cy.get(navLink("/members")).should("exist");
    cy.get(navLink("/receipts")).should("exist");
    cy.get(navLink("/activities")).should("exist");
    cy.get(navLink("/settings")).should("exist");
  });

  it("says so on the membership page rather than spinning", () => {
    // Reachable by URL even with no nav entry. It used to wait on a member that
    // never arrives and render its skeleton for good.
    cy.visit("/en/my-membership");
    cy.contains("not a club member").should("be.visible");
  });

  it("still has a profile page, without the club facts", () => {
    // The account has a person even though it has no member: name and email
    // render, the member number and the status badge do not.
    cy.visit("/en/profile");
    cy.contains("super@examplee6e3b1.com").should("be.visible");
    cy.contains("Member Number").should("not.exist");
  });

  it("can still open a member and the register", () => {
    // The regression guard. Both routes are gated on a `self.*` key and widened
    // by an administrative one, so they break the moment `self.*` stops being
    // granted to staff — which is the obvious-looking way to hide the member nav.
    cy.visit("/en/members");
    cy.get("table tbody tr").should("have.length.greaterThan", 0);
    cy.get("table tbody tr").first().click();
    cy.url().should("match", /\/members\/\d+/);
  });
});

describe("A club admin is not a club member either", { tags: ["@roles"] }, () => {
  beforeEach(() => {
    cy.loginAsAdmin();
  });

  it("has no member nav but keeps the register", () => {
    cy.get(navLink("/my-receipts")).should("not.exist");
    cy.get(navLink("/members")).should("exist");
  });
});

describe("A member still has everything", { tags: ["@roles"] }, () => {
  beforeEach(() => {
    cy.loginAsMember();
  });

  it("sees the member nav", () => {
    cy.get(navLink("/my-activities")).should("exist");
    cy.get(navLink("/my-receipts")).should("exist");
    cy.get(navLink("/my-membership")).should("exist");
  });

  it("sees its plan, not the operator's empty state", () => {
    cy.visit("/en/my-membership");
    cy.contains("not a club member").should("not.exist");
  });

  it("sees its member number on its profile", () => {
    cy.visit("/en/profile");
    cy.contains("Member Number").should("be.visible");
  });
});
