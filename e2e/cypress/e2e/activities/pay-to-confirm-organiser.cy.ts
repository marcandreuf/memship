import { TEST_ACCOUNTS } from "../../support/commands";

// The organiser's pay-to-confirm actions, end to end through the Next.js proxy.
// Every one of them passed its backend tests and was unreachable from the
// browser, because their proxy routes were missing (#591) and the refunds list
// rendered the 405 as "No refunds".
//
// Builds its own activity and registers `cardMember` in it, so no other spec's
// seats or seed data are touched, and cancels the activity afterwards.

const API = Cypress.env("API_URL") || "http://localhost:8003/api/v1";

function isoIn(days: number) {
  return new Date(Date.now() + days * 86400000).toISOString();
}

function createPaidActivity(name: string) {
  return cy
    .request("POST", `${API}/activities`, {
      name,
      starts_at: isoIn(30),
      ends_at: isoIn(31),
      registration_starts_at: isoIn(-1),
      registration_ends_at: isoIn(29),
      max_participants: 10,
      payment_methods: ["cash"],
    })
    .then((r) => {
      const id = r.body.id as number;
      cy.request("POST", `${API}/activities/${id}/prices`, { name: "Entry", amount: 20, is_default: true });
      cy.request("PUT", `${API}/activities/${id}/publish`);
      return cy.wrap(id);
    });
}

/** Register cardMember as a pending seat; yields the registration. */
function holdSeat(activityId: number) {
  cy.apiLogin(TEST_ACCOUNTS.cardMember.email, TEST_ACCOUNTS.cardMember.password);
  return cy.request(`${API}/activities/${activityId}`).then((activity) =>
    cy
      .request("POST", `${API}/activities/${activityId}/register`, { price_id: activity.body.prices[0].id })
      .then((r) => {
        expect(r.body.status).to.eq("pending");
        cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
        return cy.wrap(r.body as { id: number; receipt_id: number });
      })
  );
}

describe("Pay to confirm — organiser actions", () => {
  const name = `E2E Pay Organiser ${Date.now()}`;
  let activityId: number;

  before(() => {
    cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
    createPaidActivity(name).then((id) => {
      activityId = id;
    });
  });

  after(() => {
    cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
    cy.request({ method: "PUT", url: `${API}/activities/${activityId}/cancel`, failOnStatusCode: false });
  });

  it("confirms a pending seat without payment", () => {
    holdSeat(activityId).then((registration) => {
      cy.loginAsAdmin();
      cy.visit(`/en/activities/${activityId}`);
      cy.contains("button", "Registrations").click();
      cy.contains("tr", "Payment pending").within(() => {
        cy.contains("button", "Confirm without payment").click();
      });
      cy.get('[role="alertdialog"]').contains("button", "Confirm without payment").click();
      cy.contains("Updated").should("be.visible");

      cy.request(`${API}/activities/${activityId}/registrations?per_page=100`).then((r) => {
        const row = r.body.items.find((item: { id: number }) => item.id === registration.id);
        expect(row.status).to.eq("confirmed");
        expect(row.receipt_status).to.eq("cancelled");
      });
      // Free the member for the next test: one live registration per activity.
      cy.request("PUT", `${API}/registrations/${registration.id}/status`, { status: "cancelled" });
    });
  });

  it("lists a paid seat cancelled with a refund due, and marks it returned", () => {
    holdSeat(activityId).then((registration) => {
      cy.request("POST", `${API}/receipts/${registration.receipt_id}/pay`, { payment_method: "cash" });
      cy.request("PUT", `${API}/registrations/${registration.id}/status`, {
        status: "cancelled",
        keep_payment: false,
      });

      cy.loginAsAdmin();
      cy.visit("/en/refunds");
      cy.contains("tr", name).within(() => {
        cy.contains("button", "Mark returned").click();
      });
      cy.get('[role="alertdialog"]').contains("button", "Mark returned").click();
      cy.contains("tr", name).should("not.exist");

      cy.get('[role="combobox"]').click();
      cy.contains('[role="option"]', "Returned").click();
      cy.contains("tr", name).should("be.visible");
    });
  });
});
