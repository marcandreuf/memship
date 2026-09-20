// #245: the eye toggle on every auth password field, and the strength meter
// under the fields where a password is chosen.

describe("Password fields", () => {
  describe("show/hide toggle", () => {
    it("reveals and hides the typed password on the login form", () => {
      cy.visit("/en/login");
      cy.get('input[name="password"]').type("Secret123!").should("have.attr", "type", "password");
      cy.get('button[aria-label="Show password"]').click();
      cy.get('input[name="password"]')
        .should("have.attr", "type", "text")
        .and("have.value", "Secret123!");
      cy.get('button[aria-label="Hide password"]').click();
      cy.get('input[name="password"]').should("have.attr", "type", "password");
    });

    it("toggles each field independently on the sign up form", () => {
      cy.visit("/en/register");
      cy.get('button[aria-label="Show password"]').should("have.length", 2).first().click();
      cy.get('input[name="password"]').should("have.attr", "type", "text");
      cy.get('input[name="confirm_password"]').should("have.attr", "type", "password");
    });

    it("has the toggle on the reset password form", () => {
      cy.visit("/en/reset-password?token=e2e-placeholder");
      cy.get('button[aria-label="Show password"]').should("have.length", 2).first().click();
      cy.get('input[name="new_password"]').should("have.attr", "type", "text");
    });

    it("does not submit the form when clicked", () => {
      cy.visit("/en/login");
      cy.get('button[aria-label="Show password"]').click();
      cy.get('[data-slot="form-message"]').should("not.exist");
      cy.url().should("include", "/login");
    });
  });

  describe("strength meter", () => {
    it("is not shown on the login form", () => {
      cy.visit("/en/login");
      cy.get('[data-testid="password-strength"]').should("not.exist");
    });

    it("grades the password as it is typed on the sign up form", () => {
      cy.visit("/en/register");
      const meter = () => cy.get('[data-testid="password-strength"]');
      const field = () => cy.get('input[name="password"]');

      meter().should("exist").and("not.contain.text", "password");
      field().type("short");
      meter().should("not.contain.text", "password");
      field().clear().type("abcdefgh");
      meter().should("contain.text", "Weak password");
      field().clear().type("abcdefgh1");
      meter().should("contain.text", "Fair password");
      field().clear().type("Abcdefgh1");
      meter().should("contain.text", "Good password");
      field().clear().type("Abcdefgh1!");
      meter().should("contain.text", "Strong password");
    });

    it("is under the new password field on the reset form", () => {
      cy.visit("/en/reset-password?token=e2e-placeholder");
      cy.get('input[name="new_password"]').type("Abcdefgh1!");
      cy.get('[data-testid="password-strength"]').should("contain.text", "Strong password");
    });
  });
});
