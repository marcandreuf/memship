import { TEST_ACCOUNTS } from "../../support/commands";
import { cancelActivity, createPaidActivity, registerAs } from "../../support/pay-to-confirm";

// What the register page tells a member before they sign up for a paid seat
// (#591). Each case builds its own activity: a full one is filled by
// `cardMember`, so the member under test only reads the page.

// The payment notice belongs to a price, so it appears once one is chosen —
// and since #601 nobody has to choose. `createPaidActivity` marks its "Entry"
// price default, and the register page preselects the default price on load,
// so this opened a select that was already answered and clicked a placeholder
// that no longer renders. Asserted rather than dropped: the notices below only
// appear because a price is selected, and that is the dependency.
function priceIsPreselected() {
  cy.contains('[data-slot="select-trigger"]', "Entry").should("be.visible");
}

describe("Pay to confirm — register page", () => {
  let activityId: number | undefined;

  afterEach(() => {
    cancelActivity(activityId);
    activityId = undefined;
  });

  it("says the seat is held until paid", () => {
    createPaidActivity(`E2E Register Open ${Date.now()}`).then((id) => {
      activityId = id;
      cy.loginAsMember();
      cy.visit(`/en/activities/${id}/register`);
      cy.contains("You are eligible to register").should("be.visible");
      priceIsPreselected();
      cy.contains("Your seat will be held until you pay the receipt.").should("be.visible");
      cy.contains("button", /^Register$/).should("be.enabled");
    });
  });

  it("does not let a member register for a full activity without a waiting list", () => {
    createPaidActivity(`E2E Register Full ${Date.now()}`, { maxParticipants: 1 }).then((id) => {
      activityId = id;
      registerAs(TEST_ACCOUNTS.cardMember, id);
      cy.loginAsMember();
      cy.visit(`/en/activities/${id}/register`);
      cy.contains("This activity is full and has no waiting list.").should("be.visible");
      cy.contains("You are eligible to register").should("not.exist");
      priceIsPreselected();
      cy.contains("Your seat will be held").should("not.exist");
      cy.contains("button", /^Register$/).should("be.disabled");
    });
  });

  it("offers the waiting list when the activity is full and keeps one", () => {
    createPaidActivity(`E2E Register Waitlist ${Date.now()}`, {
      maxParticipants: 1,
      waitingList: true,
    }).then((id) => {
      activityId = id;
      registerAs(TEST_ACCOUNTS.cardMember, id);
      cy.loginAsMember();
      cy.visit(`/en/activities/${id}/register`);
      cy.contains("You can join the waiting list").should("be.visible");
      priceIsPreselected();
      cy.contains("you will join the waiting list").should("be.visible");
      cy.contains("You are eligible to register").should("not.exist");
      cy.contains("button", /^Register$/).should("be.enabled");
    });
  });
});
