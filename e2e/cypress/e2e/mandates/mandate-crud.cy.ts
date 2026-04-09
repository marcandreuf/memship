describe("Mandate List", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/mandates");
  });

  it("shows mandate list page with title", () => {
    cy.contains("h1", /mandates/i).should("be.visible");
  });

  it("shows create mandate button", () => {
    cy.contains("button", /new mandate/i).should("be.visible");
  });

  it("shows mandate table with seeded data", () => {
    cy.get("table tbody tr").should("have.length.greaterThan", 0);
  });

  it("filters mandates by status", () => {
    // Open status filter select trigger
    cy.get('[data-slot="select-trigger"]').click();
    cy.contains('[data-slot="select-item"]', "Active").click();
    cy.get("table tbody tr").should("have.length.greaterThan", 0);
  });

  it("searches mandates by name", () => {
    cy.get('input[placeholder*="Search"]').type("María");
    cy.contains("María").should("be.visible");
  });

  it("navigates to mandate detail on row click", () => {
    cy.get("table tbody tr").first().click();
    cy.url().should("match", /\/mandates\/\d+/);
  });
});

describe("Mandate Detail", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/mandates");
    cy.get("table tbody tr").first().click();
    cy.url().should("match", /\/mandates\/\d+/);
  });

  it("shows mandate detail with reference and status", () => {
    cy.contains("FAC-").should("be.visible");
    cy.contains(/active|cancelled/i).should("be.visible");
  });

  it("shows download PDF link", () => {
    cy.contains("a", /download pdf/i).should("be.visible");
  });

  it("shows signed document status", () => {
    cy.contains(/signed document|no signed document/i).should("be.visible");
  });
});

describe("Mandate Access Control", () => {
  it("member cannot see mandates page", () => {
    cy.loginAsMember();
    cy.visit("/en/mandates");
    cy.contains("h1", /mandates/i).should("not.exist");
  });
});
