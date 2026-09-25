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
// Accented on purpose: the list search must find it typed without the accent.
const SPACE = `E2E Pádel ${Date.now()}`;

// A concrete future date: 2 days ahead is always future and within the default
// 14-day booking window.
//
// Being inside the window is not enough to be on screen. The calendar opens on
// the current week (Mon-Sun of today) and renders only that, so from Saturday
// `today + 2` is next week's and every day shown is empty — `weeksAhead` below
// is what the calendar test steps through to reach it. Before that existed the
// spec failed every Saturday and Sunday and passed the rest of the week (#182).
const target = new Date();
target.setDate(target.getDate() + 2);
target.setHours(0, 0, 0, 0);

const mondayOf = (d: Date) => {
  const copy = new Date(d);
  copy.setDate(copy.getDate() - ((copy.getDay() + 6) % 7)); // 0 = Monday
  copy.setHours(0, 0, 0, 0);
  return copy;
};

// The calendar's own week heading, "DD/MM - DD/MM" over Monday to Sunday.
const ddmm = (d: Date) =>
  `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
const rangeLabel = (monday: Date) => {
  const sunday = new Date(monday);
  sunday.setDate(sunday.getDate() + 6);
  return `${ddmm(monday)} \u2013 ${ddmm(sunday)}`;
};

// How many times the calendar has to advance before the slot's week is the one
// on screen. 0 from Monday to Friday, 1 at the weekend.
const weeksAhead = Math.round(
  (mondayOf(target).getTime() - mondayOf(new Date()).getTime()) /
    (7 * 24 * 60 * 60 * 1000)
);
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

  it("admin finds the space without typing its accent", () => {
    cy.loginAsAdmin();
    cy.visit("/en/spaces");
    cy.get('input[placeholder*="Search"]').type(SPACE.replace("á", "a"));
    // The box is debounced: wait until the query is applied, or the row is
    // found in the still-unfiltered list.
    cy.url().should("include", "q=E2E");
    cy.contains("tr", SPACE).should("be.visible");
  });

  it("a search matching nothing says so, not that there are no spaces", () => {
    // It used to show the empty-club message, "No spaces yet" (#296).
    cy.loginAsAdmin();
    cy.visit("/en/spaces");
    cy.get('input[placeholder*="Search"]').type("zzqq-no-such-space");
    cy.contains("No results").should("be.visible");
    cy.contains("No spaces yet").should("not.exist");
  });

  it("admin sees a slot priced at zero as free", () => {
    cy.loginAsAdmin();
    cy.request("POST", `${API}/spaces/${spaceId}/slots`, {
      slot_date: SLOT_DATE,
      start_time: "12:00:00",
      end_time: "13:00:00",
      capacity: 1,
      price: 0,
    }).then((s) => {
      cy.visit(`/en/spaces/${spaceId}`);
      cy.contains('[role="tab"]', "Slots").click();
      // It read "€0.00" while the space itself reads "Free" (#296).
      cy.contains("tr", "12:00").should("contain.text", "Free");
      cy.request("DELETE", `${API}/spaces/${spaceId}/slots/${s.body[0].id}`);
    });
  });

  it("admin is told, in their language, why a slot was refused", () => {
    // A slot over the seeded 10:00-11:00 one. The API answers a code, not a
    // sentence, and the UI renders the translation — the English literal from
    // the raise site ("slot overlaps an existing slot") must not be what the
    // admin reads (#256).
    cy.loginAsAdmin();
    cy.visit(`/en/spaces/${spaceId}`);
    cy.contains('[role="tab"]', "Slots").click();
    cy.contains("button", "Add slot").click();
    cy.get('[role="dialog"]').within(() => {
      cy.get('input[type="date"]').clear().type(SLOT_DATE);
      cy.get('input[type="time"]').eq(0).clear().type("10:30");
      cy.get('input[type="time"]').eq(1).clear().type("11:30");
      cy.get('button[type="submit"]').click();
    });
    // Asserted on the toast element, not on visibility: the dialog is still
    // open, and Radix puts `pointer-events: none` on <body> while it is, so
    // Cypress's visibility check reads the toast as covered even though it
    // renders above the overlay.
    cy.get("[data-sonner-toast]").should(
      "contain.text",
      `The slot overlaps an existing slot (${SLOT_DATE})`
    );
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

    // Cancel is offered exactly when the API would accept it. The deadline is
    // an org setting a dev database may have changed, so the expectation is
    // read from the API rather than assumed (#296).
    cy.request(`${API}/me/bookings?scope=upcoming`).then((r) => {
      const mine = r.body.find((b: { id: number }) => b.id === bookingId);
      cy.contains("div.rounded-lg", SPACE).within(() => {
        if (mine.can_cancel) {
          cy.contains("button", "Cancel").should("be.visible");
        } else {
          cy.contains("button", "Cancel").should("not.exist");
          cy.contains("Too late to cancel").should("be.visible");
        }
      });
    });
  });

  it("member sees the booking calendar", () => {
    cy.loginAsMember();
    cy.visit("/en/book");
    cy.contains("Book a space").should("be.visible");
    // Pick this run's space explicitly — the picker defaults to the first
    // space by name, which may be another one.
    cy.get('[role="combobox"]').click();
    cy.contains('[role="option"]', SPACE).click();

    // Choosing the option sets the value but leaves the popup open under
    // Cypress's synthetic events, and an open Radix select holds
    // `pointer-events: none` on <body> — so the next click lands on a dead
    // element rather than the control it names. A real pointer closes it; this
    // one needs telling. Dismiss, then wait for the lock to lift rather than for
    // an animation, because the lock is what actually blocks.
    //
    // Nothing before this line needed it: every earlier step only reads the
    // page, and `pointer-events` does not affect an assertion.
    cy.get('[role="combobox"]').should("contain.text", SPACE);
    cy.get("body").type("{esc}");
    cy.get("body").should("not.have.css", "pointer-events", "none");

    // Step to the slot's week. Asserted rather than assumed: if the control
    // ever stops advancing a week per click, the timeout below would read as
    // "the calendar does not render slots" instead of "navigation broke".
    for (let i = 0; i < weeksAhead; i++) {
      cy.get('[aria-label="Next week"]').click();
    }
    cy.contains(rangeLabel(mondayOf(target))).should("be.visible");

    cy.contains("10:00").should("be.visible");
  });
});

// Module scope so top-level consts don't collide with other specs under the
// shared (non-isolated) Cypress tsconfig.
export {};
