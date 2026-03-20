// =============================================================================
// Memship E2E — Custom Cypress Commands
// =============================================================================

// --- Test accounts (from seed --test) ---

export const TEST_ACCOUNTS = {
  superAdmin: { email: "super@test.com", password: "TestSuper1!" },
  admin: { email: "admin@test.com", password: "TestAdmin1!" },
  member: { email: "member@test.com", password: "TestMember1!" },
};

// --- Type declarations ---

declare global {
  namespace Cypress {
    interface Chainable {
      /** Login via the login form */
      login(email: string, password: string): Chainable<void>;
      /** Login as admin (admin@test.com) */
      loginAsAdmin(): Chainable<void>;
      /** Login as super admin (super@test.com) */
      loginAsSuperAdmin(): Chainable<void>;
      /** Login as member (member@test.com) */
      loginAsMember(): Chainable<void>;
      /** Logout via the sidebar user dropdown */
      logout(): Chainable<void>;
      /** Login via API (faster, no UI) */
      apiLogin(email: string, password: string): Chainable<void>;
    }
  }
}

// --- Authentication commands ---

Cypress.Commands.add("login", (email: string, password: string) => {
  cy.visit("/en/login");
  cy.get('input[type="email"]').clear().type(email);
  cy.get('input[type="password"]').clear().type(password);
  cy.get('button[type="submit"]').click();
  cy.url().should("include", "/dashboard", { timeout: 15000 });
});

Cypress.Commands.add("loginAsAdmin", () => {
  cy.login(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
});

Cypress.Commands.add("loginAsSuperAdmin", () => {
  cy.login(TEST_ACCOUNTS.superAdmin.email, TEST_ACCOUNTS.superAdmin.password);
});

Cypress.Commands.add("loginAsMember", () => {
  cy.login(TEST_ACCOUNTS.member.email, TEST_ACCOUNTS.member.password);
});

Cypress.Commands.add("apiLogin", (email: string, password: string) => {
  const apiUrl = Cypress.env("API_URL") || "http://localhost:8003/api/v1";
  cy.request({
    method: "POST",
    url: `${apiUrl}/auth/login`,
    body: { email, password },
  }).then((resp) => {
    expect(resp.status).to.eq(200);
  });
});

Cypress.Commands.add("logout", () => {
  // Click user dropdown in sidebar footer, then logout
  cy.get('[data-slot="sidebar-footer"]').find("button").click();
  cy.contains("Sign Out").click();
  cy.url().should("include", "/login", { timeout: 10000 });
});
