// =============================================================================
// Dashboard Spaces card (#431) — shown only while `features.bookings` is on.
//
// The flag is never toggled here. It lives on the single organization_settings
// row every parallel worker shares, and turning it off would hide /spaces from
// any concurrent bookings spec (see the E2E notes in CLAUDE.md). Instead each
// test rewrites the branding response in this browser only, so both states are
// covered deterministically without touching global state.
// =============================================================================

const STATS = {
  window_days: 30,
  booked: 42,
  waitlisted: 5,
  cancelled: 3,
  total: 50,
  active_spaces: 4,
  slots: 120,
  capacity: 180,
  occupancy_pct: 23.3,
};

const withBookings = (enabled: boolean) => {
  cy.intercept("GET", "/api/settings/branding", (req) => {
    req.continue((res) => {
      res.body.features = { ...(res.body.features ?? {}), bookings: enabled };
    });
  });
};

describe("Dashboard Spaces card", () => {
  it("shows booking counts, the window and occupancy when bookings is enabled", () => {
    withBookings(true);
    cy.intercept("GET", "/api/spaces/stats", { body: STATS }).as("spaceStats");
    cy.loginAsAdmin();

    cy.wait("@spaceStats");
    cy.get('main a[href="/en/spaces"]').within(() => {
      cy.contains("Spaces").should("be.visible");
      cy.contains("Next 30 days").should("be.visible");
      cy.contains("Booked").should("be.visible");
      cy.contains("Waitlisted").should("be.visible");
      cy.contains("Cancelled").should("be.visible");
      // The header total sums the three booking rows only.
      cy.contains("50").should("be.visible");
      cy.contains("Occupancy").should("be.visible");
      cy.contains("23.3%").should("be.visible");
      cy.contains("4 spaces · 120 slots").should("be.visible");
      cy.get('[role="progressbar"]').should("have.attr", "aria-valuenow", "23.3");
    });
  });

  it("is absent and sends no /spaces request when bookings is disabled", () => {
    withBookings(false);
    cy.intercept("/api/spaces*").as("spaces");
    cy.intercept("/api/spaces/**").as("spacesNested");
    cy.intercept("GET", "/api/registrations/stats").as("regStats");
    cy.loginAsAdmin();

    // The other counter cards have loaded, so the dashboard's queries have run.
    cy.wait("@regStats");
    cy.get("main").contains("Members").should("be.visible");
    cy.get('main a[href="/en/spaces"]').should("not.exist");
    cy.get("main").contains("Next 30 days").should("not.exist");
    cy.get("@spaces.all").should("have.length", 0);
    cy.get("@spacesNested.all").should("have.length", 0);
  });
});
