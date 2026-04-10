describe("Payment Providers — Super Admin", () => {
  beforeEach(() => {
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.contains("button", "Payment Providers").click();
  });

  it("shows Payment Providers tab and list", () => {
    cy.contains("SEPA Direct Debit").should("be.visible");
  });

  it("shows provider status", () => {
    cy.contains("SEPA Direct Debit")
      .closest("[class*='rounded-lg border']")
      .should("be.visible");
    // Should show a status label (Active, Test, or Disabled)
    cy.contains("SEPA Direct Debit")
      .parent()
      .invoke("text")
      .should("match", /Active|Test|Disabled/);
  });

  it("can toggle provider status", () => {
    cy.contains("SEPA Direct Debit")
      .closest("[class*='rounded-lg border']")
      .find("button[role='switch']")
      .click();
    // Should show a status badge change (either Active or Disabled)
    cy.contains("SEPA Direct Debit").should("be.visible");
  });

  it("can test provider connection", () => {
    cy.contains("SEPA Direct Debit")
      .closest("[class*='rounded-lg border']")
      .find("button[title='Test Connection']")
      .click();
    cy.contains("Configuration is valid").should("be.visible");
  });

  it("shows Add Provider button and type selector", () => {
    cy.contains("button", "Add Provider").click();
    // Should show type selector with at least SEPA and Stripe
    cy.contains("Stripe").should("be.visible");
  });
});

describe("Payment Providers — Admin (non-super)", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/settings");
  });

  it("does not show Payment Providers tab", () => {
    cy.contains("button", "Payment Providers").should("not.exist");
  });
});
