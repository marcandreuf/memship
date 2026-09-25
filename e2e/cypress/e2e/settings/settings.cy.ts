describe("Settings — Super Admin", () => {
  beforeEach(() => {
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
  });

  it("shows settings page", () => {
    // Anchored on the heading, not a bare text match: the sidebar's own
    // "Settings" link comes first in the DOM, and `SidebarContent` scrolls, so
    // once the nav grew past the sidebar's height that label sat below its fold
    // and the assertion failed on an element the test never meant to reach.
    cy.contains("h1", "Settings").should("be.visible");
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

  it("lists Communications and Member Card once, under Members", () => {
    // Both used to be top-level tabs as well as Members sub-tabs, rendering
    // the same panels twice (#288).
    cy.get('[role="tablist"]')
      .first()
      .find('[role="tab"]')
      .then(($tabs) => {
        const labels = [...$tabs].map((tab) => tab.textContent?.trim());
        expect(labels).to.include("Members");
        expect(labels).not.to.include("Communications");
        expect(labels).not.to.include("Member Card");
      });
    cy.settingsTab("Members", "Communications");
    cy.contains("Enable announcements").should("be.visible");
    cy.settingsTab("Members", "Member Card");
    cy.contains("Enable member cards").should("be.visible");
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
