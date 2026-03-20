describe("Admin Dashboard @smoke", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
  });

  it("shows welcome message", () => {
    cy.contains("Welcome").should("be.visible");
  });

  it("shows member status chart", () => {
    cy.contains("Members").should("be.visible");
  });

  it("shows activity status chart", () => {
    cy.contains("Activities").should("be.visible");
  });

  it("shows registration stats chart", () => {
    cy.contains("Registrations").should("be.visible");
  });

  it("shows groups count", () => {
    cy.contains("Groups").should("be.visible");
  });

  it("does not show member-only content", () => {
    cy.contains("Your upcoming activities").should("not.exist");
  });
});

describe("Member Dashboard", () => {
  beforeEach(() => {
    cy.loginAsMember();
  });

  it("shows welcome message with member number", () => {
    cy.contains("Welcome").should("be.visible");
    cy.contains("member number").should("be.visible");
  });

  it("shows upcoming activities section", () => {
    cy.contains("upcoming activities").should("be.visible");
  });

  it("does not show admin charts", () => {
    cy.contains("Registrations").should("not.exist");
  });
});
