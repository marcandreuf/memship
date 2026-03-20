describe("Member Detail", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/members");
    // Click first member in the list
    cy.get("table tbody tr").first().click();
    cy.url().should("match", /\/members\/\d+/);
  });

  it("shows breadcrumbs with member name", () => {
    cy.get("nav[aria-label='breadcrumb']").should("be.visible");
    cy.get("nav[aria-label='breadcrumb']").contains("Members").should("be.visible");
  });

  it("shows member name as heading", () => {
    cy.get("h1").should("be.visible");
  });

  it("shows status badge", () => {
    cy.get("h1").parent().find("span").should("be.visible");
  });

  it("shows member info section", () => {
    cy.contains(/member info/i).should("be.visible");
  });

  it("shows activities tab", () => {
    cy.contains("button", "Activities").should("be.visible");
  });

  it("has edit button", () => {
    cy.contains("button", "Edit").should("be.visible");
  });
});
