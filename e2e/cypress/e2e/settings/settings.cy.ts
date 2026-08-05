describe("Settings — Super Admin", () => {
  beforeEach(() => {
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
  });

  it("shows settings page", () => {
    cy.contains("Settings").should("be.visible");
  });

  it("shows organization settings form", () => {
    cy.contains("Organization").should("be.visible");
    cy.get('input[name="name"]').should("be.visible");
  });

  it("shows branding section with brand color", () => {
    cy.contains("Brand").should("be.visible");
    cy.get('input[type="color"], input[name="brand_color"]').should("be.visible");
  });

  it("shows membership types tab", () => {
    // Membership Types is a sub-tab of Members, not a top-level tab.
    cy.settingsTab("Members", "Membership Types");
    cy.contains("Full Member").should("be.visible");
    cy.contains("Student").should("be.visible");
  });
});

describe("Settings — Admin (non-super)", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/settings");
  });

  it("shows membership types tab", () => {
    cy.contains("Membership Types").should("be.visible");
  });
});
