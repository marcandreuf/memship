import { TEST_ACCOUNTS } from "../../support/commands";

describe("Login @smoke", () => {
  beforeEach(() => {
    cy.visit("/en/login");
  });

  it("shows login form", () => {
    cy.contains("Log in");
    cy.get('input[type="email"]').should("be.visible");
    cy.get('input[type="password"]').should("be.visible");
    cy.get('button[type="submit"]').should("be.visible");
  });

  it("shows forgot password and register links", () => {
    cy.contains("Forgot your password?").should("be.visible");
    cy.contains("Sign up").should("be.visible");
  });

  it("logs in with valid admin credentials", () => {
    cy.get('input[type="email"]').type(TEST_ACCOUNTS.admin.email);
    cy.get('input[type="password"]').type(TEST_ACCOUNTS.admin.password);
    cy.get('button[type="submit"]').click();
    cy.url().should("include", "/dashboard");
    cy.contains("Welcome").should("be.visible");
  });

  it("logs in with valid member credentials", () => {
    cy.get('input[type="email"]').type(TEST_ACCOUNTS.member.email);
    cy.get('input[type="password"]').type(TEST_ACCOUNTS.member.password);
    cy.get('button[type="submit"]').click();
    cy.url().should("include", "/dashboard");
  });

  // #191: addresses are stored and compared in lower case. Nothing else in the
  // suite signs in with a spelling other than the seeded one, so without these
  // the form schema could go back to rejecting what the API accepts — or the
  // API to a case-sensitive lookup — with everything still green.
  it("logs in with the address spelled in a different case", () => {
    cy.get('input[type="email"]').type(TEST_ACCOUNTS.admin.email.toUpperCase());
    cy.get('input[type="password"]').type(TEST_ACCOUNTS.admin.password);
    cy.get('button[type="submit"]').click();
    cy.url().should("include", "/dashboard");
  });

  it("logs in with an address padded with whitespace", () => {
    // `type="email"` strips surrounding whitespace in the browser before the
    // form schema sees it, so this asserts the whole path rather than the
    // schema's trim: what a paste with stray spaces actually does.
    cy.get('input[type="email"]')
      .type(`  ${TEST_ACCOUNTS.admin.email}  `)
      .should("have.value", TEST_ACCOUNTS.admin.email);
    cy.get('input[type="password"]').type(TEST_ACCOUNTS.admin.password);
    cy.get('button[type="submit"]').click();
    cy.url().should("include", "/dashboard");
  });

  it("shows error with invalid credentials", () => {
    cy.get('input[type="email"]').type("wrong@examplee6e3b1.com");
    cy.get('input[type="password"]').type("WrongPassword1!");
    cy.get('button[type="submit"]').click();
    cy.get('[class*="destructive"]').should("be.visible");
  });

  it("redirects unauthenticated user to login", () => {
    cy.visit("/en/dashboard");
    cy.url().should("include", "/login");
  });
});

describe("Logout @smoke", () => {
  it("logs out and redirects to login", () => {
    cy.loginAsAdmin();
    cy.logout();
    cy.url().should("include", "/login");
  });
});
