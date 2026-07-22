// =============================================================================
// Simple Bookings — super admin enables the module + creates a space and a
// weekly slot (capacity 2), an admin manages it, a member books an upcoming
// occurrence and sees it in My Bookings, and the booking calendar renders.
//
// Data setup uses the API where it must be deterministic (space/slot/booking);
// the settings toggle and the read-side pages are exercised through the UI.
// The multi-member waitlist + FIFO promotion path is covered by the backend
// integration tests (only one member seed account exists).
// =============================================================================

const API = Cypress.env("API_URL") || "http://localhost:8003/api/v1";
const SPACE = `E2E Court ${Date.now()}`;

// A concrete future occurrence: 2 days ahead is always future and within the
// default 14-day window; its weekday is what the slot is created on.
const target = new Date();
target.setDate(target.getDate() + 2);
target.setHours(0, 0, 0, 0);
const WEEKDAY = (target.getDay() + 6) % 7; // 0 = Monday
const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")}`;
const BOOKING_DATE = iso(target);

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
        if ($sw.attr("aria-checked") !== "true") cy.wrap($sw).click();
      });
    cy.contains(/saved successfully/i).should("be.visible");

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
          weekday: WEEKDAY,
          start_time: "10:00:00",
          end_time: "11:00:00",
          capacity: 2,
        },
      }).then((s) => {
        expect(s.status).to.eq(201);
        slotId = s.body.id;
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
    cy.contains("tr", SPACE).contains("a", "Manage").click();
    cy.url().should("match", /\/spaces\/\d+/);
    cy.contains("10:00").should("be.visible");
  });

  it("member books an upcoming slot and sees it in My Bookings", () => {
    cy.loginAsMember();
    cy.request({
      method: "POST",
      url: `${API}/bookings`,
      body: { space_slot_id: slotId, booking_date: BOOKING_DATE },
    }).then((r) => {
      expect(r.status).to.eq(201);
      expect(r.body.status).to.eq("booked");
      bookingId = r.body.id;
    });

    cy.visit("/en/my-bookings");
    cy.contains(SPACE).should("be.visible");
    cy.contains("Booked").should("be.visible");
  });

  it("member sees the booking calendar", () => {
    cy.loginAsMember();
    cy.visit("/en/book");
    cy.contains("Book a space").should("be.visible");
    cy.contains(SPACE).should("exist");
  });
});

// Module scope so top-level consts don't collide with other specs under the
// shared (non-isolated) Cypress tsconfig.
export {};
