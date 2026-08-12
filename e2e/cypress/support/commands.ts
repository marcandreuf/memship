// =============================================================================
// Memship E2E — Custom Cypress Commands
// =============================================================================

// --- Test accounts (from seed --test) ---

export const TEST_ACCOUNTS = {
  superAdmin: { email: "super@examplee6e3b1.com", password: "TestSuper1!" },
  admin: { email: "admin@examplee6e3b1.com", password: "TestAdmin1!" },
  member: { email: "member@examplee6e3b1.com", password: "TestMember1!" },
  // Holds the seeded `treasurer` custom role: billing.* and nothing else. The
  // three system roles cannot express a partial admin, so this is the only
  // account that exercises permission-driven nav.
  treasurer: { email: "treasurer@examplee6e3b1.com", password: "TestTreasurer1!" },
};

// --- Type declarations ---

declare global {
  namespace Cypress {
    interface Chainable {
      /** Login via the login form */
      login(email: string, password: string): Chainable<void>;
      /** Login as admin (admin@examplee6e3b1.com) */
      loginAsAdmin(): Chainable<void>;
      /** Login as super admin (super@examplee6e3b1.com) */
      loginAsSuperAdmin(): Chainable<void>;
      /** Login as member (member@examplee6e3b1.com) */
      loginAsMember(): Chainable<void>;
      /** Login as the narrow custom role (treasurer@examplee6e3b1.com) */
      loginAsTreasurer(): Chainable<void>;
      /** Logout via the sidebar user dropdown */
      logout(): Chainable<void>;
      /** Login via API (faster, no UI) */
      apiLogin(email: string, password: string): Chainable<void>;
      /**
       * Select a settings tab. Settings nests sub-tabs inside parent tabs, so
       * a leaf like "Payment Providers" is only in the DOM once its parent is
       * open. Pass the parent alone for a top-level tab, or parent + child.
       */
      settingsTab(parent: string, child?: string): Chainable<void>;
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

Cypress.Commands.add("loginAsTreasurer", () => {
  cy.login(TEST_ACCOUNTS.treasurer.email, TEST_ACCOUNTS.treasurer.password);
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

// --- Navigation commands ---

Cypress.Commands.add("settingsTab", (parent: string, child?: string) => {
  // The parent list is the first tablist on the page; sub-tab lists render
  // inside whichever parent panel is active, so scope the child to that panel
  // rather than matching a label that may also exist at the top level.
  cy.contains('[role="tab"]', parent).click();
  if (child) {
    cy.get('[role="tabpanel"][data-state="active"]')
      .contains('[role="tab"]', child)
      .click();
  }
});

// --- Authentication commands (cont.) ---

Cypress.Commands.add("logout", () => {
  // Click user dropdown in sidebar footer, then logout
  cy.get('[data-slot="sidebar-footer"]').find("button").click();
  cy.contains("Sign Out").click();
  // Headroom for runs against `next dev`, where /login is compiled on first
  // request and 4 parallel workers share one server — that pushes this
  // redirect past 10s and makes the test flaky. Against a production build
  // it resolves quickly; the allowance only matters for local dev runs.
  cy.url().should("include", "/login", { timeout: 30000 });
});
