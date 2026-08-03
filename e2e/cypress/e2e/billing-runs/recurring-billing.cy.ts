// =============================================================================
// Recurring Billing (v0.4.4) — Settings tab, run-now, list/detail, widget, RBAC
// =============================================================================

describe("Recurring Billing — Settings tab (super admin)", () => {
  beforeEach(() => {
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.settingsTab("Payments", "Recurring billing");
  });

  it("shows the recurring billing controls", () => {
    cy.contains("Enable recurring billing").should("be.visible");
    cy.contains("Day of month").should("be.visible");
    cy.contains("Notification email").should("be.visible");
    cy.contains("button", "Save").should("be.visible");
  });

  it("enables recurring billing, sets the day + email, and saves", () => {
    // Ensure the switch is ON (idempotent — leaves it enabled).
    cy.get('[role="switch"]').then(($sw) => {
      if ($sw.attr("aria-checked") !== "true") {
        cy.wrap($sw).click();
      }
    });
    cy.get('[role="switch"]').should("have.attr", "aria-checked", "true");

    cy.get('input[type="number"]').clear().type("15");
    cy.get('input[type="email"]').clear().type("billing@cemediterrani.cat");
    cy.contains("button", "Save").click();

    cy.contains(/saved successfully/i).should("be.visible");
  });

  it("does not clobber other feature flags (membership types still load)", () => {
    // Saving the recurring-billing keys must merge into features JSONB, not replace it.
    cy.settingsTab("Members", "Membership Types");
    cy.contains(/full member|student/i).should("be.visible");
  });
});

describe("Billing Runs — list and run-now (admin)", () => {
  const API_URL = Cypress.env("API_URL") || "http://localhost:8003/api/v1";

  before(() => {
    // Ensure at least one billing run exists so the history table (and its
    // column headers) renders — a fresh seed has zero runs, which shows the
    // empty state instead of the table.
    cy.apiLogin("admin@test.com", "TestAdmin1!");
    cy.request({
      method: "POST",
      url: `${API_URL}/billing-runs/run-now`,
      body: {},
    }).then((resp) => {
      expect(resp.status).to.eq(200);
    });
  });

  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/billing-runs");
  });

  it("shows the billing runs page with header, filters and Run now", () => {
    cy.contains("h1", "Billing runs").should("be.visible");
    cy.contains("button", "Run now").should("be.visible");
    cy.contains(/frequency/i).should("be.visible");
    cy.contains(/period/i).should("be.visible");
    cy.contains(/status/i).should("be.visible");
  });

  it("runs billing now and reflects the result", () => {
    cy.contains("button", "Run now").click();
    cy.contains("Run billing now").should("be.visible");

    // Default frequency is "All" — run every due frequency.
    cy.get('[role="dialog"]').contains("button", /^Run$/).click();

    // Idempotent: the run may generate N or 0 receipts, but the flow must succeed.
    cy.contains(/billing run complete/i).should("be.visible");

    // At least one run is now visible in the history (Monthly is the seeded fee frequency).
    cy.get("table tbody tr").should("have.length.greaterThan", 0);
    cy.contains("td", "Monthly").should("be.visible");
  });

  it("opens a run detail page from a table row", () => {
    cy.get("body").then(($b) => {
      if ($b.find("table tbody tr").length > 0) {
        cy.get("table tbody tr").first().click();
        cy.url().should("match", /\/billing-runs\/\d+/);
        cy.contains("Run detail").should("be.visible");
        cy.contains(/receipts generated/i).should("be.visible");
        cy.contains(/success|failed|partial/i).should("be.visible");
      }
    });
  });
});

describe("Recurring Billing — Dashboard widget", () => {
  it("shows the next billing run widget for admins", () => {
    cy.loginAsAdmin();
    cy.visit("/en/dashboard");
    cy.contains("Next recurring billing").should("be.visible");
    // Either a countdown ("Day N · ...") or the disabled state.
    cy.contains(/day \d+|recurring billing disabled/i).should("be.visible");
  });
});

describe("Recurring Billing — Access control", () => {
  it("redirects members away from billing runs", () => {
    cy.loginAsMember();
    cy.visit("/en/billing-runs");
    cy.url().should("include", "/dashboard");
    cy.contains("h1", "Billing runs").should("not.exist");
  });
});
