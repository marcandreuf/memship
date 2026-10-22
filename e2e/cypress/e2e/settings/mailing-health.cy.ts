// Each provider card says whether its credentials are known to work (#338).
// The mailing config is stubbed rather than written: it is global state, and a
// real write would overwrite whatever credentials the instance has on file.
const health = (status: string, extra: Record<string, string | null> = {}) => ({
  status,
  last_success_at: null,
  last_failure_at: null,
  last_failure: null,
  ...extra,
});

const view = (resendHealth: ReturnType<typeof health>) => ({
  active_provider: null,
  resend: {
    from_email: "",
    api_key: { configured: true, last4: "4f2a" },
    ready: true,
    health: resendHealth,
  },
  gmail: {
    user: "",
    from_email: "",
    app_password: { configured: false, last4: null },
    ready: false,
    health: health("unverified"),
  },
  secrets_encryption_available: true,
  sources: {},
});

function visitWith(body: ReturnType<typeof view>) {
  cy.intercept("GET", "/api/settings/mailing", body).as("mailing");
  cy.loginAsSuperAdmin();
  cy.visit("/en/settings");
  cy.settingsTab("Integrations", "Mailing");
  cy.wait("@mailing");
}

describe("Mailing provider health", () => {
  it("asks for a test when the credentials have never been tried", () => {
    visitWith(view(health("unverified")));
    cy.get('[data-testid="mailing-resend-health"]')
      .should("have.attr", "data-status", "unverified")
      .and("contain.text", "Not verified");
    // A provider without credentials has nothing to verify.
    cy.get('[data-testid="mailing-gmail-health"]').should("not.exist");
  });

  it("reports working credentials", () => {
    visitWith(view(health("ok", { last_success_at: "2026-10-20T09:30:00Z" })));
    cy.get('[data-testid="mailing-resend-health"]')
      .should("have.attr", "data-status", "ok")
      .and("contain.text", "Working");
  });

  it("names the reason credentials are failing", () => {
    visitWith(
      view(
        health("failing", {
          last_failure_at: "2026-10-21T09:30:00Z",
          last_failure: "invalid_credentials",
        }),
      ),
    );
    cy.get('[data-testid="mailing-resend-health"]')
      .should("have.attr", "data-status", "failing")
      .and("contain.text", "The provider rejected the credentials.");
  });
});
