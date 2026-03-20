describe("Activity List — Admin", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/activities");
  });

  it("shows activity list page with title", () => {
    cy.contains("h1", "Activities").should("be.visible");
  });

  it("shows create activity button for admin", () => {
    cy.contains("button", /new activity/i).should("be.visible");
  });

  it("shows activity table with data", () => {
    cy.get("table thead").should("be.visible");
    cy.get("table tbody tr").should("have.length.greaterThan", 0);
  });

  it("displays seeded activities", () => {
    cy.get('input[placeholder*="Search"]').type("Soccer");
    cy.contains("Summer Soccer Camp").should("be.visible");
  });

  it("shows all statuses for admin via filter", () => {
    // Admin can filter to see draft activities
    cy.get("select, [role='combobox']").first().click();
    cy.contains("Draft").click();
    cy.contains("Annual Gala Dinner").should("be.visible");
  });

  it("filters by search", () => {
    cy.get('input[placeholder*="Search"]').type("Soccer");
    cy.contains("Summer Soccer Camp").should("be.visible");
    cy.contains("Yoga Workshop").should("not.exist");
  });

  it("navigates to activity detail on row click", () => {
    cy.get('input[placeholder*="Search"]').type("Soccer");
    cy.contains("Summer Soccer Camp").click();
    cy.url().should("match", /\/activities\/\d+/);
    cy.contains("h1", "Summer Soccer Camp").should("be.visible");
  });
});

describe("Activity List — Member", () => {
  beforeEach(() => {
    cy.loginAsMember();
    cy.visit("/en/activities");
  });

  it("shows published activities as cards", () => {
    cy.contains("Summer Soccer Camp").should("be.visible");
  });

  it("does not show draft activities", () => {
    cy.contains("Annual Gala Dinner").should("not.exist");
  });

  it("does not show create button", () => {
    cy.contains("button", /new activity/i).should("not.exist");
  });
});
