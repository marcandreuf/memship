// Approving a registration says whether the applicant was told (#332). The
// approval is real; only the notification in the response is stubbed, because
// what the instance's mail transport does is not this spec's to decide.
function approvePendingApplicant(notification: { status: string; reason: string | null }) {
  const email = `approve-${Date.now()}-${Cypress._.random(1e6)}@examplee6e3b1.com`;
  cy.request("POST", "/api/auth/register", {
    first_name: "Approve",
    last_name: "Notify",
    email,
    password: "Approve-Notify-2026!",
  });

  cy.loginAsAdmin();
  cy.request(`/api/members?status=pending&search=${encodeURIComponent(email)}`)
    .its("body.items.0.id")
    .then((id) => {
      cy.intercept("POST", `/api/members/${id}/approve`, (req) => {
        req.continue((res) => {
          res.body.notification = notification;
        });
      }).as("approve");
      cy.visit(`/en/members/${id}`);
    });

  cy.contains("button", "Approve").click();
  cy.get('[role="dialog"]').contains("button", "Approve").click();
  cy.wait("@approve").its("response.body.member.status").should("eq", "active");
  cy.get('[role="dialog"]').should("not.exist");
}

describe("Approving a registration reports the notification", () => {
  it("confirms the applicant was notified when the mail went out", () => {
    approvePendingApplicant({ status: "sent", reason: null });
    cy.contains("The applicant has been notified by email").should("be.visible");
  });

  it("warns, with the reason, when the mail could not be delivered", () => {
    approvePendingApplicant({ status: "failed", reason: "invalid_credentials" });
    cy.contains("Registration approved, but the applicant was NOT notified").should("be.visible");
    cy.contains("The mail provider rejected its credentials").should("be.visible");
    cy.contains("The applicant has been notified by email").should("not.exist");
  });

  it("warns when the approval notice is switched off", () => {
    approvePendingApplicant({ status: "suppressed", reason: null });
    cy.contains("the approval notice is switched off").should("be.visible");
  });
});
