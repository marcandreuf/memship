describe("Activity Detail — Admin", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/activities");
    cy.get('input[placeholder*="Search"]').type("Soccer");
    cy.contains("Summer Soccer Camp").click();
    cy.url().should("match", /\/activities\/\d+/);
  });

  it("shows breadcrumbs", () => {
    cy.get("nav[aria-label='breadcrumb']").within(() => {
      cy.contains("Activities").should("be.visible");
      cy.contains("Summer Soccer Camp").should("be.visible");
    });
  });

  it("shows activity name and status badge", () => {
    cy.contains("h1", "Summer Soccer Camp").should("be.visible");
    cy.contains(/published/i).should("be.visible");
  });

  it("shows basic information section", () => {
    cy.contains("Basic Information").should("be.visible");
    cy.contains("Main Stadium").should("be.visible");
  });

  it("shows all entity tabs", () => {
    cy.contains("button", "Modalities").should("be.visible");
    cy.contains("button", "Prices").should("be.visible");
    cy.contains("button", "Registrations").should("be.visible");
    cy.contains("button", "Discounts").should("be.visible");
    cy.contains("button", "Consents").should("be.visible");
    cy.contains("button", "Attachments").should("be.visible");
  });

  it("shows modalities tab with data", () => {
    cy.contains("button", "Modalities").click();
    cy.contains("Morning Only").should("be.visible");
    cy.contains("Full Day").should("be.visible");
  });

  it("shows prices tab with data", () => {
    cy.contains("button", "Prices").click();
    cy.contains("Early Bird").should("be.visible");
    cy.contains("General").should("be.visible");
  });

  it("shows registrations tab with data", () => {
    cy.contains("button", "Registrations").click();
    cy.get("table").should("be.visible");
  });

  it("shows lifecycle action buttons", () => {
    cy.contains("button", /archive/i).should("be.visible");
    cy.contains("button", /cancel/i).should("be.visible");
  });

  it("has edit button for basic info", () => {
    cy.contains("button", "Edit").should("be.visible");
  });
});
