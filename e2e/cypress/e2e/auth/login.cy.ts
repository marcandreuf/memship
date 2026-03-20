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

  it("shows error with invalid credentials", () => {
    cy.get('input[type="email"]').type("wrong@test.com");
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
