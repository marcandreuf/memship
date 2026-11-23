// =============================================================================
// Pay-to-confirm space bookings (#603): a paid booking is held until paid.
//
// The spec builds its own paid space and slot through the API and removes them
// afterwards. It switches the bookings module and the three booking mails a
// paid space needs on, never off: global settings every other worker reads,
// and on is what every reader wants (see CLAUDE.md, E2E).
//
// Deadlines, the sweep, the waiting-list bands and late payments are the
// backend tests' to hold; this covers what the screens show and do.
// =============================================================================

import { TEST_ACCOUNTS } from "../../support/commands";

const API = Cypress.env("API_URL") || "http://localhost:8003/api/v1";
const SPACE = `E2E Paid court ${Date.now()}`;
const BOOKING_MAILS = [
  "booking_pending_payment",
  "booking_deadline_reminder",
  "booking_cancelled_unpaid",
];

// Three days ahead is always in the future and inside the default window, and
// leaves the hold far above the club's shortest one.
const day = new Date();
day.setDate(day.getDate() + 3);
const SLOT_DATE = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(
  day.getDate()
).padStart(2, "0")}`;

type Booking = { id: number; status: string };

function bookAsMember(slotId: number) {
  cy.apiLogin(TEST_ACCOUNTS.member.email, TEST_ACCOUNTS.member.password);
  return cy
    .request("POST", `${API}/bookings`, { space_slot_id: slotId })
    .then((r) => cy.wrap(r.body as Booking));
}

function cancelAsAdmin(bookingId: number) {
  cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
  cy.request({ method: "DELETE", url: `${API}/bookings/${bookingId}`, failOnStatusCode: false });
}

function receiptOf(spaceId: number, bookingId: number) {
  cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
  return cy
    .request(`${API}/spaces/${spaceId}/bookings`)
    .then((r) => cy.wrap(r.body.items.find((b: { id: number }) => b.id === bookingId).receipt_id as number));
}

describe("Pay-to-confirm space bookings", () => {
  let spaceId: number;
  let slotId: number;
  const bookings: number[] = [];

  before(() => {
    cy.apiLogin(TEST_ACCOUNTS.superAdmin.email, TEST_ACCOUNTS.superAdmin.password);
    cy.request("PUT", `${API}/settings/`, { features: { bookings: true } });
    cy.request("PUT", `${API}/settings/communications`, {
      templates: Object.fromEntries(BOOKING_MAILS.map((k) => [k, true])),
    });
    cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
    cy.request("POST", `${API}/spaces`, {
      name: SPACE,
      space_type: "court",
      description: null,
      open_time: "08:00:00",
      close_time: "22:00:00",
      price: 10,
      payment_methods: ["cash"],
    }).then((r) => {
      expect(r.body.payment_flow).to.eq("pay_to_confirm");
      spaceId = r.body.id;
      cy.request("POST", `${API}/spaces/${spaceId}/slots`, {
        slot_date: SLOT_DATE,
        start_time: "10:00:00",
        end_time: "11:00:00",
        capacity: 1,
      }).then((s) => {
        slotId = s.body[0].id;
      });
    });
  });

  // Each test starts from a free slot, so a retry never inherits the booking
  // a failed attempt left behind.
  beforeEach(() => {
    if (!spaceId) return;
    cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
    cy.request(`${API}/spaces/${spaceId}/bookings`).then((r) => {
      r.body.items
        .filter((b: Booking) => b.status !== "cancelled")
        .forEach((b: Booking) => cancelAsAdmin(b.id));
    });
  });

  after(() => {
    if (!spaceId) return;
    // A refund owed blocks the delete, so settle it first, then remove the space.
    cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
    bookings.forEach((id) => {
      cy.request({ method: "DELETE", url: `${API}/bookings/${id}`, failOnStatusCode: false });
      cy.request({
        method: "POST",
        url: `${API}/seats/booking/${id}/refund-returned`,
        failOnStatusCode: false,
      });
    });
    cy.request({ method: "DELETE", url: `${API}/spaces/${spaceId}?force=true`, failOnStatusCode: false });
  });

  it("tells the member the booking is held until paid, and until when", () => {
    cy.loginAsMember();
    cy.visit(`/en/book?space=${spaceId}&date=${SLOT_DATE}`);
    cy.contains("div.rounded-md", "10:00").within(() => {
      cy.contains("button", "Book").click();
    });
    cy.get('[role="alertdialog"]').within(() => {
      cy.contains("held until you pay").should("be.visible");
      cy.contains("button", "Book").click();
    });
    cy.contains("Booking held: pay the receipt to confirm it").should("be.visible");

    cy.visit("/en/my-bookings");
    cy.contains("div.rounded-lg", SPACE).within(() => {
      cy.contains("Awaiting payment").should("be.visible");
      cy.contains("Pay before").should("be.visible");
      cy.contains("button", /pay now/i).click();
    });
    cy.url().should("include", "/my-receipts");

    cy.apiLogin(TEST_ACCOUNTS.member.email, TEST_ACCOUNTS.member.password);
    cy.request(`${API}/me/bookings?scope=upcoming`).then((r) => {
      const mine = r.body.find((b: { space_id: number }) => b.space_id === spaceId);
      expect(mine.status).to.eq("pending");
      bookings.push(mine.id);
      cancelAsAdmin(mine.id);
    });
  });

  it("lets the club confirm a pending booking without payment", () => {
    bookAsMember(slotId).then((booking) => {
      bookings.push(booking.id);
      expect(booking.status).to.eq("pending");

      cy.loginAsAdmin();
      cy.visit(`/en/spaces/${spaceId}`);
      cy.contains('[role="tab"]', "Bookings").click();
      cy.contains("tr", "Awaiting payment").within(() => {
        cy.contains("Pay by").should("be.visible");
        cy.contains("button", "Confirm without payment").click();
      });
      cy.get('[role="alertdialog"]').contains("button", "Confirm without payment").click();
      cy.contains("tr", "Booked").should("be.visible");
      cy.contains("tr", "Awaiting payment").should("not.exist");

      cancelAsAdmin(booking.id);
    });
  });

  it("sends a paid booking the club cancels to Refunds", () => {
    bookAsMember(slotId).then((booking) => {
      bookings.push(booking.id);
      receiptOf(spaceId, booking.id).then((receiptId) => {
        cy.request("POST", `${API}/receipts/${receiptId}/pay`, { payment_method: "cash" });
      });

      cy.loginAsAdmin();
      cy.visit(`/en/spaces/${spaceId}`);
      cy.contains('[role="tab"]', "Bookings").click();
      cy.contains("tr", "Booked").within(() => {
        cy.contains("button", "Cancel").click();
      });
      cy.get('[role="dialog"]').within(() => {
        cy.contains("This booking is paid").should("be.visible");
        cy.contains("button", "Back").should("be.visible");
        cy.contains("button", "Cancel").click();
      });
      cy.contains("tr", "Refund due").should("be.visible");

      cy.visit("/en/refunds");
      cy.contains("tr", SPACE).within(() => {
        cy.contains("Booking").should("be.visible");
      });
    });
  });

  it("shows the space's payment settings and the club's paid-bookings block", () => {
    cy.loginAsAdmin();
    cy.visit(`/en/spaces/${spaceId}`);
    cy.contains("Accepted payment methods").should("be.visible");
    cy.contains("Cash").should("be.visible");
    cy.contains("button", "Edit").click();
    cy.contains("Release unpaid bookings earlier").should("be.visible");

    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.settingsTab("Payments", "General");
    cy.contains("Paid bookings").should("be.visible");
    cy.contains("Margin before the slot (minutes)").should("be.visible");
  });
});
