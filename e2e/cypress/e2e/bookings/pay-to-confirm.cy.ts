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

import {
  API,
  SLOT_DATE,
  bookAs,
  createPaidSpace,
  enablePaidSpaces,
  receiptOf,
  removeSpace,
  type Booking,
} from "../../support/space-pay-to-confirm";

const SPACE = `E2E Paid court ${Date.now()}`;
const bookAsMember = (slotId: number) => bookAs(TEST_ACCOUNTS.member, slotId);

function cancelAsAdmin(bookingId: number) {
  cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
  cy.request({ method: "DELETE", url: `${API}/bookings/${bookingId}`, failOnStatusCode: false });
}

describe("Pay-to-confirm space bookings", () => {
  let spaceId: number;
  let slotId: number;

  before(() => {
    enablePaidSpaces();
    createPaidSpace(SPACE).then((created) => {
      spaceId = created.spaceId;
      slotId = created.slotId;
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

  after(() => removeSpace(spaceId));

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
      cancelAsAdmin(mine.id);
    });
  });

  it("lets the club confirm a pending booking without payment", () => {
    bookAsMember(slotId).then((booking) => {
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
