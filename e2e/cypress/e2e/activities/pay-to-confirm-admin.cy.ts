// The seed stamps its catalogue legacy, as an upgrade does, except the drafts
// and Private Wine Tasting, which use pay-to-confirm with cash (#591).
// Read-only: nothing here writes settings or registrations.

function openActivity(search: string, name: string) {
  cy.visit("/en/activities");
  cy.get('input[placeholder*="Search"]').type(search);
  // Wait for the search to land in the URL: its debounced replace would
  // otherwise undo the navigation the click starts.
  cy.location("search").should("include", `q=${search}`);
  cy.contains(name).click();
  cy.url().should("match", /\/activities\/\d+/);
}

describe("Pay to confirm — admin", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
  });

  it("marks a legacy activity in the list and not one on the new flow", () => {
    cy.visit("/en/activities");
    cy.get('input[placeholder*="Search"]').type("Soccer");
    cy.contains("tr", "Summer Soccer Camp").contains("legacy").should("be.visible");

    cy.get('input[placeholder*="Search"]').clear().type("Wine");
    cy.contains("tr", "Private Wine Tasting").should("not.contain", "legacy");
  });

  it("marks a legacy activity in its header", () => {
    openActivity("Soccer", "Summer Soccer Camp");
    cy.contains("h1", "Summer Soccer Camp").parent().contains("legacy").should("be.visible");
  });

  it("shows how a pay-to-confirm activity is paid", () => {
    openActivity("Wine", "Private Wine Tasting");
    cy.contains("Accepted payment methods").should("be.visible");
    cy.contains("Cash").should("be.visible");
  });

  it("shows the payment column in the registrations tab", () => {
    openActivity("Soccer", "Summer Soccer Camp");
    cy.contains("button", "Registrations").click();
    cy.contains("th", "Payment").should("be.visible");
  });

  it("opens the refund list from the activities page", () => {
    cy.visit("/en/activities");
    cy.contains("a", "Refunds").click();
    cy.url().should("match", /\/en\/refunds$/);
    cy.contains("h1", "Refunds").should("be.visible");
  });
});
