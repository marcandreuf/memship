// The return pages used to promise "we'll email you when it's confirmed" even
// when the gateway's notification was refused and no email could come. They now
// say only what is known, and after the wait that no confirmation has arrived
// (#514). The status calls are stubbed: this is about what the page says, not
// about the gateway. The waits are real — `cy.clock` before the visit also
// freezes the timers the page needs to make its first request.
describe("Payment return pages — unconfirmed payment", () => {
  const pendingReceipt = {
    id: 999001,
    receipt_number: "FAC-E2E-PENDING",
    status: "emitted",
    total_amount: "30.00",
    redsys_auth_code: null,
  };

  beforeEach(() => {
    cy.loginAsMember();
  });

  it("Redsys: no email promise, then says the confirmation has not arrived", () => {
    cy.intercept("GET", "/api/receipts/*/redsys/return*", pendingReceipt).as("status");
    cy.visit(`/en/payment/redsys/return?receipt_id=${pendingReceipt.id}&outcome=ok`);
    cy.wait("@status");

    cy.contains("Processing payment...").should("be.visible");
    cy.contains("as soon as the gateway confirms it").should("be.visible");
    cy.contains(/email/i).should("not.exist");

    // The page polls for ~30s before saying the confirmation has not come.
    cy.contains("Payment awaiting confirmation", { timeout: 45_000 }).should("be.visible");
    cy.contains("don't pay again").should("be.visible");
  });

  it("Stripe: says the confirmation has not arrived once polling stops", () => {
    cy.intercept("GET", "/api/receipts/by-stripe-session/*", pendingReceipt).as("status");
    cy.visit("/en/payment/success?session_id=cs_test_e2e_pending");
    cy.wait("@status");

    cy.contains("as soon as the gateway confirms it").should("be.visible");

    cy.contains("Payment awaiting confirmation", { timeout: 25_000 }).should("be.visible");
    cy.contains("don't pay again").should("be.visible");
  });

  it("a confirmed payment still reads as success", () => {
    cy.intercept("GET", "/api/receipts/*/redsys/return*", {
      ...pendingReceipt,
      status: "paid",
      redsys_auth_code: "123456",
    }).as("status");
    cy.visit(`/en/payment/redsys/return?receipt_id=${pendingReceipt.id}&outcome=ok`);
    cy.wait("@status");

    cy.contains(/payment.*success|payment.*confirmed/i).should("be.visible");
    cy.contains("Payment awaiting confirmation").should("not.exist");
  });
});
