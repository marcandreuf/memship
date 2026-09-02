// =============================================================================
// Simple Bookings — super admin enables the module + creates a space and a
// dated slot (capacity 2), an admin manages it, a member books it and sees it
// in My Bookings, and the booking calendar renders. Slots live on concrete
// dates; a repeat rule materializes a series (checked via the API).
//
// Data setup uses the API where it must be deterministic (space/slot/booking);
// the settings toggle and the read-side pages are exercised through the UI.
// The multi-member waitlist + FIFO promotion path is covered by the backend
// integration tests (only one member seed account exists).
// =============================================================================

const API = Cypress.env("API_URL") || "http://localhost:8003/api/v1";
const SPACE = `E2E Court ${Date.now()}`;

// A concrete future date: 2 days ahead is always future and within the
// default 14-day booking window.
const target = new Date();
target.setDate(target.getDate() + 2);
target.setHours(0, 0, 0, 0);
const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")}`;
const SLOT_DATE = iso(target);

describe("Simple Bookings", () => {
  let spaceId: number;
  let slotId: number;
  let bookingId: number | undefined;

  before(() => {
    // Enable the module via the settings UI (persists in org settings).
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.contains('[role="tab"]', "Bookings").click();
    cy.get('[role="switch"]')
      .first()
      .then(($sw) => {
        // Only click (and expect the save toast) when it isn't already on —
        // a dev/demo database may have the module enabled.
        if ($sw.attr("aria-checked") !== "true") {
          cy.wrap($sw).click();
          cy.contains(/saved successfully/i).should("be.visible");
        }
      });

    // Deterministic data via the API.
    cy.request({
      method: "POST",
      url: `${API}/spaces`,
      body: {
        name: SPACE,
        space_type: "court",
        description: null,
        open_time: "08:00:00",
        close_time: "22:00:00",
      },
    }).then((r) => {
      expect(r.status).to.eq(201);
      spaceId = r.body.id;
      cy.request({
        method: "POST",
        url: `${API}/spaces/${spaceId}/slots`,
        body: {
          slot_date: SLOT_DATE,
          start_time: "10:00:00",
          end_time: "11:00:00",
          capacity: 2,
        },
      }).then((s) => {
        // Slot creation returns the list of created slots (one, no repeat).
        expect(s.status).to.eq(201);
        expect(s.body).to.have.length(1);
        slotId = s.body[0].id;
      });
    });
  });

  after(() => {
    // Don't leave the shared seed member holding a booking.
    if (bookingId) {
      cy.loginAsMember();
      cy.request({
        method: "DELETE",
        url: `${API}/bookings/${bookingId}`,
        failOnStatusCode: false,
      });
    }
    // Remove the space itself — leftovers from prior runs otherwise pile up
    // in the member's space picker. force clears any remaining bookings.
    if (spaceId) {
      cy.loginAsAdmin();
      cy.request({
        method: "DELETE",
        url: `${API}/spaces/${spaceId}?force=true`,
        failOnStatusCode: false,
      });
    }
  });

  it("shows the Bookings settings group (super admin)", () => {
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.contains('[role="tab"]', "Bookings").click();
    cy.contains("Enable bookings").should("be.visible");
    cy.contains("Booking rules").should("be.visible");
  });

  it("admin sees the space and its slot", () => {
    cy.loginAsAdmin();
    cy.visit("/en/spaces");
    cy.contains(SPACE).should("be.visible");
    cy.contains("tr", SPACE).click();
    cy.url().should("match", /\/spaces\/\d+/);
    cy.contains("10:00").should("be.visible");
  });

  it("admin creates a repeating series via the API", () => {
    // A week out so every generated occurrence is in the future; cleaned up
    // immediately (no bookings → no force needed).
    const seriesStart = new Date();
    seriesStart.setDate(seriesStart.getDate() + 7);
    cy.loginAsAdmin();
    cy.request({
      method: "POST",
      url: `${API}/spaces/${spaceId}/slots`,
      body: {
        slot_date: iso(seriesStart),
        start_time: "18:00:00",
        end_time: "19:00:00",
        capacity: 1,
        repeat: {
          weekdays: [(seriesStart.getDay() + 6) % 7],
          interval_weeks: 1,
          count: 3,
        },
      },
    }).then((s) => {
      expect(s.status).to.eq(201);
      expect(s.body).to.have.length(3);
      const seriesIds = new Set(s.body.map((x: { series_id: string }) => x.series_id));
      expect(seriesIds.size).to.eq(1);
      s.body.forEach((x: { id: number }) =>
        cy.request("DELETE", `${API}/spaces/${spaceId}/slots/${x.id}`)
      );
    });
  });

  it("member books the slot and sees it in My Bookings", () => {
    cy.loginAsMember();
    cy.request({
      method: "POST",
      url: `${API}/bookings`,
      body: { space_slot_id: slotId },
    }).then((r) => {
      expect(r.status).to.eq(201);
      expect(r.body.status).to.eq("booked");
      bookingId = r.body.id;
    });

    cy.visit("/en/my-bookings");
    cy.contains(SPACE).should("be.visible");
    cy.contains("Booked").should("be.visible");
    // Occupancy shows seats taken / capacity.
    cy.contains("1/2").should("be.visible");
  });

  it("member sees the booking calendar", () => {
    cy.loginAsMember();
    cy.visit("/en/book");
    cy.contains("Book a space").should("be.visible");
    // Pick this run's space explicitly — the picker defaults to the first
    // space by name, which may be another one.
    cy.get('[role="combobox"]').click();
    cy.contains('[role="option"]', SPACE).click();
    cy.contains("10:00").should("be.visible");
  });
});

// Module scope so top-level consts don't collide with other specs under the
// shared (non-isolated) Cypress tsconfig.
export {};
