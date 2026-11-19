import { TEST_ACCOUNTS } from "../../support/commands";
import { cancelActivity, createPaidActivity, registerAs } from "../../support/pay-to-confirm";

// Private Wine Tasting is seeded pay-to-confirm with cash (#591). The member's
// registration is made and removed through the API, so a rerun starts clean and
// no other spec sees a seat taken.

const API = Cypress.env("API_URL") || "http://localhost:8003/api/v1";

function wineTastingId() {
  return cy
    .request(`${API}/activities?search=Wine&status=published`)
    .then((r) => r.body.items.find((a: { name: string }) => a.name === "Private Wine Tasting").id as number);
}

function cancelMySeat(activityId: number) {
  cy.request(`${API}/members/me/registrations?per_page=100`).then((r) => {
    r.body.items
      .filter((reg: { activity_id: number; status: string }) => reg.activity_id === activityId && reg.status !== "cancelled")
      .forEach((reg: { id: number }) => cy.request("DELETE", `${API}/registrations/${reg.id}`));
  });
}

describe("Pay to confirm — member", () => {
  let activityId: number;

  beforeEach(() => {
    cy.loginAsMember();
    wineTastingId().then((id) => {
      activityId = id;
      cancelMySeat(id);
      cy.request(`${API}/activities/${id}`).then((activity) => {
        cy.request(`${API}/activities/${id}/consents`).then((consents) => {
          cy.request("POST", `${API}/activities/${id}/register`, {
            price_id: activity.body.prices[0].id,
            consents: consents.body
              .filter((c: { is_mandatory: boolean }) => c.is_mandatory)
              .map((c: { id: number }) => ({ activity_consent_id: c.id, accepted: true })),
          })
            .its("body.status")
            .should("eq", "pending");
        });
      });
    });
  });

  afterEach(() => {
    cancelMySeat(activityId);
  });

  it("shows the seat as held until paid, with a way to pay", () => {
    cy.visit(`/en/activities/${activityId}`);
    cy.contains("Your seat is held").should("be.visible");
    cy.contains("button", /pay now/i).click();
    cy.url().should("include", "/my-receipts");
  });

  it("offers only what a cash-only seat accepts in My receipts", () => {
    // The receipt of a cash-only seat used to show the card and Bizum buttons.
    cy.request(`${API}/members/me/registrations?per_page=100`).then((regs) => {
      const seat = regs.body.items.find(
        (reg: { activity_id: number; status: string }) => reg.activity_id === activityId && reg.status === "pending"
      );
      cy.request(`${API}/members/me/receipts?per_page=100`).then((receipts) => {
        const receipt = receipts.body.items.find(
          (r: { registration_id: number | null }) => r.registration_id === seat.id
        );
        cy.visit("/en/my-receipts");
        cy.contains("th", "Due Date").should("be.visible");
        cy.contains("tr", receipt.receipt_number).within(() => {
          cy.contains("Awaiting payment").should("be.visible");
          cy.contains("You can pay it in cash at the club.").should("be.visible");
          cy.get("button").should("not.exist");
        });
      });
    });
  });

  it("shows it in My activities too", () => {
    cy.visit("/en/my-activities");
    cy.contains("a", "Payment pending").within(() => {
      cy.contains("Private Wine Tasting").should("be.visible");
      cy.contains("button", /pay now/i).should("be.visible");
    });
  });
});

describe("Pay to confirm — member cancels a held seat", () => {
  let activityId: number | undefined;

  afterEach(() => {
    cancelActivity(activityId);
    activityId = undefined;
  });

  it("asks in the member's own words, with a way back", () => {
    const name = `E2E Member Cancel ${Date.now()}`;
    createPaidActivity(name, { allowSelfCancellation: true }).then((id) => {
      activityId = id;
      registerAs(TEST_ACCOUNTS.member, id).its("status").should("eq", "pending");

      cy.loginAsMember();
      cy.visit("/en/my-activities");
      cy.contains("a", name).within(() => {
        cy.contains("button", "Cancel").click();
      });
      cy.get('[role="alertdialog"]').within(() => {
        cy.contains("You will no longer be registered").should("be.visible");
        cy.contains("button", "Back").click();
      });
      cy.contains("a", name).contains("Payment pending").should("be.visible");

      cy.contains("a", name).within(() => {
        cy.contains("button", "Cancel").click();
      });
      cy.get('[role="alertdialog"]').contains("button", "Cancel Registration").click();
      cy.contains("Updated").should("be.visible");
    });
  });
});
