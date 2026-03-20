describe("Group List", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/groups");
  });

  it("shows group list page with title", () => {
    cy.contains("h1", "Groups").should("be.visible");
  });

  it("shows create group button", () => {
    cy.contains("button", "Create Group").should("be.visible");
  });

  it("displays seeded groups", () => {
    cy.contains("Adult Members").should("be.visible");
    cy.contains("Youth Programs").should("be.visible");
    cy.contains("Senior Members").should("be.visible");
    cy.contains("Honorary Members").should("be.visible");
  });

  it("navigates to group detail on row click", () => {
    cy.contains("Adult Members").click();
    cy.url().should("match", /\/groups\/\d+/);
    cy.contains("Adult Members").should("be.visible");
  });
});

describe("Group Detail", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/groups");
    cy.contains("Adult Members").click();
  });

  it("shows group name and detail", () => {
    cy.contains("h1", "Adult Members").should("be.visible");
  });

  it("shows membership types tab", () => {
    cy.contains("button", "Membership Types").should("be.visible");
    cy.contains("button", "Membership Types").click();
    cy.get("table").should("be.visible");
  });

  it("shows members tab", () => {
    cy.contains("button", "Members").should("be.visible");
    cy.contains("button", "Members").click();
    cy.get("table").should("be.visible");
  });
});
