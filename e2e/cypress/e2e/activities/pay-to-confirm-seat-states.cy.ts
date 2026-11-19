import { TEST_ACCOUNTS } from "../../support/commands";
import { cancelActivity, createPaidActivity, payInCash, registerAs } from "../../support/pay-to-confirm";

// What the organiser may do to a seat depends on whether it owes money (#591):
// a seat that owes is confirmed by paying or waiving, never by a status flip,
// and a paid seat is neither sent back to wait nor cancelled without deciding
// what happens to the money. Both rules were found by hand in the validation.

function openRegistrations(activityId: number) {
  cy.loginAsAdmin();
  cy.visit(`/en/activities/${activityId}`);
  cy.contains("button", "Registrations").click();
}

function openStatusMenu(rowText: string) {
  cy.contains("tr", rowText).within(() => {
    cy.contains("button", "Change Status").click();
  });
}

describe("Pay to confirm — seat states in the registrations tab", () => {
  let activityId: number;

  beforeEach(() => {
    createPaidActivity(`E2E Seat States ${Date.now()}`).then((id) => {
      activityId = id;
    });
  });

  afterEach(() => {
    cancelActivity(activityId);
  });

  it("does not offer Confirmed for a seat that still owes payment", () => {
    registerAs(TEST_ACCOUNTS.cardMember, activityId).its("status").should("eq", "pending");

    openRegistrations(activityId);
    openStatusMenu("Payment pending");
    cy.get('[role="listbox"]').within(() => {
      cy.contains('[role="option"]', "Confirmed").should("not.exist");
      cy.contains('[role="option"]', "Waitlisted").should("exist");
      cy.contains('[role="option"]', "Cancelled").should("exist");
    });
  });

  it("does not offer Waitlisted for a paid seat, and asks before cancelling it", () => {
    registerAs(TEST_ACCOUNTS.cardMember, activityId).then((registration) => {
      payInCash(registration.receipt_id as number);
    });

    openRegistrations(activityId);
    openStatusMenu("Confirmed");
    cy.get('[role="listbox"]').within(() => {
      cy.contains('[role="option"]', "Waitlisted").should("not.exist");
    });
    // By keyboard: the lone option opens right over the trigger, and Radix takes
    // a click at the spot that opened the list for the end of the opening one.
    cy.contains('[role="option"]', "Cancelled").focus().trigger("keydown", { key: "Enter" });

    cy.get('[role="dialog"]').within(() => {
      cy.contains("This registration is paid").should("be.visible");
      cy.contains("Keep the payment").should("be.visible");
      cy.contains("button", "Back").click();
    });
    cy.get('[role="dialog"]').should("not.exist");
    cy.contains("tr", "Confirmed").should("be.visible");
  });
});
