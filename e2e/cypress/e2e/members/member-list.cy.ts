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

  it("finds a member by the full name the table shows", () => {
    cy.get('input[placeholder*="Search"]').type("María García");
    cy.url().should("include", "q=Mar");
    cy.get("table tbody tr").should("have.length", 1);
    cy.get("table tbody tr").first().should("contain", "María García");
  });

  it("drops the filter when the search is edited below 3 characters", () => {
    cy.get('input[placeholder*="Search"]').type("María García");
    cy.get("table tbody tr").should("have.length", 1);

    cy.get('input[placeholder*="Search"]').clear().type("Ma");

    cy.get('input[placeholder*="Search"]').should("have.value", "Ma");
    cy.url().should("not.include", "q=");
    cy.get("table tbody tr").should("have.length.greaterThan", 1);
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
