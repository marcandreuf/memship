// =============================================================================
// Pay-to-confirm space bookings (#603): the paths around a held booking that
// pay-to-confirm.cy.ts does not walk. Found missing by a manual test pass.
//
// Every test builds its own paid space through the API and the spec removes
// them all afterwards. Global settings are only switched on (CLAUDE.md, E2E).
// What depends on the clock — the shortest hold, a slot too close to its
// start — is driven by stubbing the API's answer, not by the time of day the
// suite happens to run at. Deadlines, the sweep and the waiting-list bands are
// the backend tests'.
// =============================================================================

import { TEST_ACCOUNTS } from "../../support/commands";
import {
  API,
  SECOND_MEMBER,
  SLOT_DATE,
  bookAs,
  createPaidSpace,
  enablePaidSpaces,
  payInCash,
  receiptOf,
  removeSpace,
} from "../../support/space-pay-to-confirm";

const spaces: number[] = [];
const uniqueName = (label: string) => `E2E Held ${label} ${Date.now()}`;

/** A paid space with one 10:00 slot, removed after the spec. */
function paidSpace(label: string, options?: { methods?: string[]; capacity?: number }) {
  const name = uniqueName(label);
  return createPaidSpace(name, options).then(({ spaceId, slotId }) => {
    spaces.push(spaceId);
    return cy.wrap({ name, spaceId, slotId });
  });
}

function openBookingsTab(spaceId: number) {
  cy.loginAsAdmin();
  cy.visit(`/en/spaces/${spaceId}`);
  cy.contains('[role="tab"]', "Bookings").click();
}

describe("Pay-to-confirm space bookings: around the held booking", () => {
  before(() => enablePaidSpaces());

  after(() => spaces.forEach((id) => removeSpace(id)));

  it("books the booking once the club marks its receipt paid", () => {
    paidSpace("pay").then(({ name, spaceId, slotId }) => {
      bookAs(TEST_ACCOUNTS.member, slotId).then((booking) => {
        receiptOf(spaceId, booking.id).then((receiptId) => {
          cy.loginAsAdmin();
          cy.visit(`/en/receipts/${receiptId}`);
          cy.contains("button", "Mark Paid").click();
          cy.get('[role="dialog"]').within(() => {
            cy.get('[role="combobox"]').click();
          });
          cy.get('[role="option"]').filter(":visible").contains("Cash").click();
          cy.get('[role="dialog"]').contains("button", "Mark Paid").click();
          cy.get('[role="dialog"]').should("not.exist");

          cy.visit(`/en/spaces/${spaceId}`);
          cy.contains('[role="tab"]', "Bookings").click();
          cy.contains("tr", "Booked").should("be.visible");

          cy.loginAsMember();
          cy.visit("/en/my-bookings");
          cy.contains("div.rounded-lg", name).within(() => {
            cy.contains("Booked").should("be.visible");
            cy.contains("button", /pay now/i).should("not.exist");
          });
        });
      });
    });
  });

  it("offers in My receipts only the ways the space accepts", () => {
    paidSpace("cash", { methods: ["cash"] }).then(({ slotId }) => {
      bookAs(TEST_ACCOUNTS.member, slotId).then((booking) => {
        cy.request(`${API}/me/bookings?scope=upcoming`).then((mine) => {
          const held = mine.body.find((b: { id: number }) => b.id === booking.id);
          cy.request(`${API}/members/me/receipts?per_page=100`).then((receipts) => {
            const receipt = receipts.body.items.find(
              (r: { id: number }) => r.id === held.receipt_id
            );
            cy.loginAsMember();
            cy.visit("/en/my-receipts");
            cy.contains("tr", receipt.receipt_number).within(() => {
              cy.contains("Awaiting payment").should("be.visible");
              cy.contains("You can pay it in cash at the club.").should("be.visible");
              cy.get("button").should("not.exist");
            });
          });
        });
      });
    });
  });

  it("shows a slot too close to its start to be held as too late", () => {
    paidSpace("late").then(({ spaceId, slotId }) => {
      cy.intercept("GET", `/api/spaces/${spaceId}/availability*`, (req) => {
        req.continue((res) => {
          res.body.cells.forEach((cell: { space_slot_id: number; cell_state: string }) => {
            if (cell.space_slot_id === slotId) cell.cell_state = "too_late";
          });
        });
      });
      cy.loginAsMember();
      cy.visit(`/en/book?space=${spaceId}&date=${SLOT_DATE}`);
      cy.contains("div.rounded-md", "10:00").within(() => {
        cy.contains("Too late to book").should("be.visible");
        cy.contains("button", "Book").should("not.exist");
      });
    });
  });

  it("explains a booking refused for too short a hold, and refreshes the week", () => {
    paidSpace("refused").then(({ spaceId }) => {
      cy.intercept("GET", `/api/spaces/${spaceId}/availability*`).as("week");
      cy.intercept("POST", "/api/bookings", {
        statusCode: 422,
        body: {
          detail: {
            code: "booking_hold_too_short",
            message: "Too close to the slot to hold it until paid",
            pay_by: new Date().toISOString(),
            cutoff_minutes: 60,
          },
        },
      }).as("book");
      cy.loginAsMember();
      cy.visit(`/en/book?space=${spaceId}&date=${SLOT_DATE}`);
      cy.wait("@week");
      cy.contains("div.rounded-md", "10:00").within(() => {
        cy.contains("button", "Book").click();
      });
      cy.get('[role="alertdialog"]').contains("button", "Book").click();
      cy.wait("@book");
      cy.contains("too late to book this slot").should("be.visible");
      cy.contains("60 minutes before it starts").should("be.visible");
      // The week is fetched again, so the slot does not keep offering Book.
      cy.wait("@week");
    });
  });

  it("filters the Bookings tab to the bookings awaiting payment", () => {
    paidSpace("filter", { capacity: 2 }).then(({ spaceId, slotId }) => {
      bookAs(TEST_ACCOUNTS.member, slotId);
      bookAs(SECOND_MEMBER, slotId).then((second) => payInCash(spaceId, second.id));

      openBookingsTab(spaceId);
      cy.contains("tr", "Booked").should("be.visible");
      cy.get('[role="tabpanel"] [role="combobox"]').first().click();
      cy.contains('[role="option"]', "Awaiting payment").click();
      cy.contains("tr", "Awaiting payment").should("be.visible");
      cy.contains("tr", "Booked").should("not.exist");
    });
  });

  it("keeps a paid booking's money out of Refunds when the club keeps it", () => {
    paidSpace("keep").then(({ name, spaceId, slotId }) => {
      bookAs(TEST_ACCOUNTS.member, slotId).then((booking) => payInCash(spaceId, booking.id));

      openBookingsTab(spaceId);
      cy.contains("tr", "Booked").within(() => cy.contains("button", "Cancel").click());
      cy.get('[role="dialog"]').within(() => {
        cy.contains("Keep the payment").click();
        cy.contains("button", "Cancel").click();
      });
      cy.contains("tr", "Cancelled").should("be.visible");
      cy.contains("tr", "Refund due").should("not.exist");

      cy.visit("/en/refunds");
      cy.contains("h1", "Refunds").should("be.visible");
      cy.contains("tr", name).should("not.exist");
    });
  });

  it("moves a returned refund from Due to Returned", () => {
    paidSpace("returned").then(({ name, spaceId, slotId }) => {
      bookAs(TEST_ACCOUNTS.member, slotId).then((booking) => {
        payInCash(spaceId, booking.id);
        cy.request("DELETE", `${API}/bookings/${booking.id}`);
      });

      cy.loginAsAdmin();
      cy.visit("/en/refunds");
      cy.contains("tr", name).within(() => cy.contains("button", "Mark returned").click());
      cy.get('[role="alertdialog"]').contains("button", "Mark returned").click();
      cy.contains("tr", name).should("not.exist");

      cy.get('[role="combobox"]').click();
      cy.contains('[role="option"]', "Returned").click();
      cy.contains("tr", name).should("be.visible");
    });
  });

  it("puts a booking awaiting payment on the member's dashboard", () => {
    paidSpace("dashboard").then(({ name, slotId }) => {
      bookAs(TEST_ACCOUNTS.member, slotId);
      cy.loginAsMember();
      cy.visit("/en/dashboard");
      cy.contains("Bookings awaiting payment")
        .closest("[data-slot='card'], .rounded-xl, .rounded-lg")
        .within(() => {
          cy.contains(name).should("be.visible");
          cy.contains("a", /pay now/i).should("have.attr", "href").and("include", "/my-receipts");
        });
    });
  });

  it("refuses to delete a slot whose booking was paid, and says why", () => {
    paidSpace("delete").then(({ spaceId, slotId }) => {
      bookAs(TEST_ACCOUNTS.member, slotId).then((booking) => payInCash(spaceId, booking.id));

      cy.loginAsAdmin();
      cy.visit(`/en/spaces/${spaceId}`);
      cy.contains('[role="tab"]', "Slots").click();
      cy.contains("tr", "10:00").within(() => cy.contains("button", "Delete").click());
      cy.get('[role="alertdialog"]').contains("button", "Delete").click();
      cy.contains("carrying a payment").should("be.visible");
      cy.contains("tr", "10:00").should("be.visible");
    });
  });

  it("refuses a priced space with no way to pay", () => {
    cy.loginAsAdmin();
    cy.visit("/en/spaces");
    cy.contains("button", "New space").click();
    cy.get('[role="dialog"]').within(() => {
      cy.get('input[name="name"]').type(uniqueName("no-methods"));
      cy.get('input[name="price"]').type("10");
      cy.get('button[type="submit"]').click();
    });
    cy.contains("[data-sonner-toast]", "A paid space must accept at least one payment method.")
      .should("have.length", 1);
  });

  it("keeps the club's actions in reach on a phone", () => {
    paidSpace("phone").then(({ spaceId, slotId }) => {
      bookAs(TEST_ACCOUNTS.member, slotId);
      cy.viewport(390, 844);
      cy.loginAsAdmin();
      cy.visit(`/en/spaces/${spaceId}`);
      // On a phone the tabs collapse into a Sections menu.
      cy.get('[aria-label="Sections"]').click();
      cy.get('[role="option"]').filter(":visible").contains("Bookings").click();
      cy.contains("div.rounded-lg", "Awaiting payment").within(() => {
        cy.contains("Pay by").should("be.visible");
        cy.contains("button", "Confirm without payment").should("be.visible");
        cy.contains("button", "Cancel").should("be.visible");
      });
    });
  });
});
