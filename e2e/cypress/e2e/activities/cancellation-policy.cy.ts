import { TEST_ACCOUNTS } from "../../support/commands";
import { cancelActivity, createPaidActivity, payInCash, registerAs } from "../../support/pay-to-confirm";

// What a member's own cancellation does to a payment already made (#604).
// Each test builds its own activity and cancels it afterwards. The activity
// starts in 30 days, so a 60-minute deadline is still ahead and a 45-day one
// is already behind.

const IN_TIME = { deadlineMinutes: 60, lateMode: "block" } as const;
const LATE_KEEP = { deadlineMinutes: 45 * 24 * 60, lateMode: "allow_no_refund" } as const;
const LATE_BLOCK = { deadlineMinutes: 45 * 24 * 60, lateMode: "block" } as const;

function paidSeat(name: string, cancellationPolicy: typeof IN_TIME | typeof LATE_KEEP | typeof LATE_BLOCK) {
  return createPaidActivity(name, { allowSelfCancellation: true, cancellationPolicy }).then((id) =>
    registerAs(TEST_ACCOUNTS.member, id).then((registration) => {
      payInCash(registration.receipt_id as number);
      return cy.wrap(id);
    })
  );
}

describe("Cancellation policy — a member cancels a paid seat", () => {
  let activityId: number | undefined;

  afterEach(() => {
    cancelActivity(activityId);
    activityId = undefined;
  });

  it("inside the deadline the payment is owed back", () => {
    const name = `E2E Policy In Time ${Date.now()}`;
    paidSeat(name, IN_TIME).then((id) => {
      activityId = id;
      cy.loginAsMember();
      cy.visit("/en/my-activities");
      cy.contains("a", name).within(() => cy.contains("button", "Cancel").click());
      cy.get('[role="alertdialog"]').within(() => {
        cy.contains("will not be returned").should("not.exist");
        cy.contains("button", "Cancel Registration").click();
      });
      cy.contains("Updated").should("be.visible");

      cy.loginAsAdmin();
      cy.visit("/en/refunds");
      cy.contains("tr", name).should("be.visible");
    });
  });

  it("past it, when the club allows it, warns and keeps the payment", () => {
    const name = `E2E Policy Late Keep ${Date.now()}`;
    paidSeat(name, LATE_KEEP).then((id) => {
      activityId = id;
      cy.loginAsMember();
      cy.visit("/en/my-activities");
      cy.contains("a", name).within(() => cy.contains("button", "Cancel").click());
      cy.get('[role="alertdialog"]').within(() => {
        cy.contains("will not be returned").should("be.visible");
        cy.contains("button", "Cancel Registration").click();
      });
      cy.contains("Updated").should("be.visible");

      cy.loginAsAdmin();
      cy.visit("/en/refunds");
      cy.contains("th", "Reference").should("be.visible");
      cy.contains("tr", name).should("not.exist");
    });
  });

  it("past it, when the club refuses, offers no cancel button", () => {
    const name = `E2E Policy Late Block ${Date.now()}`;
    paidSeat(name, LATE_BLOCK).then((id) => {
      activityId = id;
      cy.loginAsMember();
      cy.visit("/en/my-activities");
      cy.contains("a", name).should("be.visible");
      cy.contains("a", name).within(() => cy.contains("button", "Cancel").should("not.exist"));
    });
  });
});
