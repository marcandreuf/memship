describe("Stripe Checkout — Happy Path @smoke", () => {
  const API_URL = Cypress.env("API_URL") || "http://localhost:8003/api/v1";
  let emittedReceiptId: number;

  before(() => {
    // Login as admin via API and create an emitted receipt for the member test account
    cy.apiLogin("admin@test.com", "TestAdmin1!");

    // Find member ID for member@test.com
    cy.request({
      method: "GET",
      url: `${API_URL}/members?search=member@test.com`,
    }).then((membersResp) => {
      expect(membersResp.status).to.eq(200);
      const member = membersResp.body.items[0];
      expect(member).to.exist;

      // Create a receipt for this member
      cy.request({
        method: "POST",
        url: `${API_URL}/receipts`,
        body: {
          member_id: member.id,
          description: "Stripe E2E test receipt",
          base_amount: 50.0,
          vat_rate: 21,
          origin: "manual",
        },
      }).then((createResp) => {
        expect(createResp.status).to.eq(201);
        const receiptId = createResp.body.id;

        // Emit the receipt so it becomes payable
        cy.request({
          method: "POST",
          url: `${API_URL}/receipts/${receiptId}/emit`,
        }).then((emitResp) => {
          expect(emitResp.status).to.eq(200);
          expect(emitResp.body.status).to.eq("emitted");
          emittedReceiptId = receiptId;
        });
      });
    });
  });

  beforeEach(() => {
    cy.loginAsMember();
  });

  it("shows Pay Now button on emitted receipt", () => {
    cy.visit("/en/my-receipts");
    cy.contains("h1", /my receipts/i).should("be.visible");
    cy.contains("Stripe E2E test receipt").should("be.visible");
    cy.contains("button", /pay now/i).should("be.visible");
  });

  it("calls Stripe checkout API when Pay Now is clicked", () => {
    const fakeSessionId = "cs_test_fake_session_123";
    const fakeRedirectUrl = "https://checkout.stripe.com/pay/cs_test_fake";

    // Intercept the Next.js proxy route for Stripe checkout
    cy.intercept("POST", `/api/receipts/*/stripe/checkout`, {
      statusCode: 200,
      body: {
        redirect_url: fakeRedirectUrl,
        session_id: fakeSessionId,
      },
    }).as("stripeCheckout");

    cy.visit("/en/my-receipts");
    cy.contains("Stripe E2E test receipt")
      .closest("tr")
      .find("button")
      .contains(/pay now/i)
      .click();

    // Verify the checkout API was called
    cy.wait("@stripeCheckout").then((interception) => {
      expect(interception.response?.statusCode).to.eq(200);
      expect(interception.response?.body.redirect_url).to.eq(fakeRedirectUrl);
      expect(interception.response?.body.session_id).to.eq(fakeSessionId);
    });
  });

  it("payment success page shows confirmation after webhook", () => {
    const fakeSessionId = "cs_test_success_page_456";

    // Simulate the webhook marking the receipt as paid (via admin API)
    cy.apiLogin("admin@test.com", "TestAdmin1!");
    cy.request({
      method: "POST",
      url: `${API_URL}/receipts/${emittedReceiptId}/pay`,
      body: {
        payment_method: "card",
        payment_date: new Date().toISOString().split("T")[0],
      },
    }).then((payResp) => {
      expect(payResp.status).to.eq(200);
      expect(payResp.body.status).to.eq("paid");
    });

    // Now login as member and visit the success page
    cy.loginAsMember();

    // Intercept the session lookup to return our paid receipt
    cy.intercept("GET", `/api/receipts/by-stripe-session/${fakeSessionId}`, {
      statusCode: 200,
      body: {
        id: emittedReceiptId,
        receipt_number: "REC-TEST-001",
        status: "paid",
        total_amount: 60.5,
        description: "Stripe E2E test receipt",
      },
    }).as("sessionLookup");

    cy.visit(`/en/payment/success?session_id=${fakeSessionId}`);

    // Should show success confirmation
    cy.wait("@sessionLookup");
    cy.contains(/payment.*success|payment.*confirmed/i).should("be.visible");
    cy.contains("REC-TEST-001").should("be.visible");

    // Should show navigation back to receipts
    cy.contains("button", /back to receipts|view receipt/i).should("be.visible");
  });

  it("receipt shows paid status in My Receipts after payment", () => {
    cy.visit("/en/my-receipts");
    cy.contains("Stripe E2E test receipt")
      .closest("tr")
      .within(() => {
        cy.contains(/paid/i).should("be.visible");
        // Pay Now button should not be visible for paid receipts
        cy.contains("button", /pay now/i).should("not.exist");
      });
  });
});
