import { TEST_ACCOUNTS } from "../../support/commands";
import { cancelActivity, createPaidActivity, registerAs } from "../../support/pay-to-confirm";

// What the register page tells a member before they sign up for a paid seat
// (#591). Each case builds its own activity: a full one is filled by
// `cardMember`, so the member under test only reads the page.

// The payment notice belongs to a price, so it appears once one is chosen.
function choosePrice() {
  cy.contains("button", "Select a price").click();
  cy.contains('[role="option"]', "Entry").focus().trigger("keydown", { key: "Enter" });
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
      choosePrice();
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
      choosePrice();
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
      choosePrice();
      cy.contains("you will join the waiting list").should("be.visible");
      cy.contains("You are eligible to register").should("not.exist");
      cy.contains("button", /^Register$/).should("be.enabled");
    });
  });
});
