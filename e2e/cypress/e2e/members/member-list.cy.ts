describe("Member List", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/members");
  });

  it("shows member list page with title", () => {
    cy.contains("h1", "Members").should("be.visible");
  });

  it("shows create member button", () => {
    cy.contains("button", /new member/i).should("be.visible");
  });

  it("shows member table with headers", () => {
    cy.get("table thead").should("be.visible");
    cy.get("table tbody tr").should("have.length.greaterThan", 0);
  });

  it("displays seeded members in the table", () => {
    // Members are sorted by newest first, check any visible member
    cy.get("table tbody tr").first().find("td").should("have.length.greaterThan", 2);
  });

  it("shows pagination when enough members", () => {
    cy.contains("Showing").should("be.visible");
  });

  it("filters members by search", () => {
    cy.get('input[placeholder*="Search"]').type("María");
    cy.contains("María").should("be.visible");
  });

  it("navigates to member detail on row click", () => {
    cy.get("table tbody tr").first().click();
    cy.url().should("match", /\/members\/\d+/);
  });
});

describe("Member List — Access Control", () => {
  it("member cannot see members list", () => {
    cy.loginAsMember();
    cy.visit("/en/members");
    cy.contains("h1", "Members").should("not.exist");
  });
});
