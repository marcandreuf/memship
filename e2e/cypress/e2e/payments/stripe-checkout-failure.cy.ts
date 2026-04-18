describe("Stripe Checkout — Failure / Cancel Path", () => {
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
          description: "Stripe cancel E2E test receipt",
          base_amount: 30.0,
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

  describe("Cancel Page UI", () => {
    beforeEach(() => {
      cy.loginAsMember();
    });

    it("shows cancellation message when user returns from Stripe", () => {
      const fakeSessionId = "cs_test_cancelled_789";

      // Intercept session lookup — receipt is still emitted (not paid)
      cy.intercept("GET", `/api/receipts/by-stripe-session/${fakeSessionId}`, {
        statusCode: 200,
        body: {
          id: emittedReceiptId,
          receipt_number: "REC-CANCEL-001",
          status: "emitted",
          total_amount: 36.3,
          description: "Stripe cancel E2E test receipt",
        },
      }).as("sessionLookup");

      cy.visit(`/en/payment/cancel?session_id=${fakeSessionId}`);

      // Should show cancellation message
      cy.contains(/cancel/i).should("be.visible");

      // Should show back to receipts button
      cy.contains("button", /back to receipts/i).should("be.visible");
    });

    it("navigates back to My Receipts from cancel page", () => {
      const fakeSessionId = "cs_test_cancelled_nav_101";

      cy.intercept("GET", `/api/receipts/by-stripe-session/${fakeSessionId}`, {
        statusCode: 200,
        body: {
          id: emittedReceiptId,
          receipt_number: "REC-CANCEL-002",
          status: "emitted",
          total_amount: 36.3,
          description: "Stripe cancel E2E test receipt",
        },
      }).as("sessionLookup");

      cy.visit(`/en/payment/cancel?session_id=${fakeSessionId}`);
      cy.contains("button", /back to receipts/i).click();
      cy.url().should("include", "/my-receipts");
    });
  });

  describe("Expired Session — Receipt Returned", () => {
    it("receipt is marked returned after session expiry (via admin return)", () => {
      // Simulate what happens when checkout.session.expired webhook fires:
      // the webhook handler marks the receipt as returned.
      // We simulate this by calling the return endpoint as admin.
      cy.apiLogin("admin@test.com", "TestAdmin1!");
      cy.request({
        method: "POST",
        url: `${API_URL}/receipts/${emittedReceiptId}/return`,
        body: {
          return_reason: "Stripe checkout session expired",
        },
      }).then((returnResp) => {
        expect(returnResp.status).to.eq(200);
        expect(returnResp.body.status).to.eq("returned");
      });

      // Login as member and verify the receipt shows returned status
      cy.loginAsMember();
      cy.visit("/en/my-receipts");
      cy.contains("Stripe cancel E2E test receipt")
        .closest("tr")
        .within(() => {
          cy.contains(/returned/i).should("be.visible");
          // Pay Now button should not be visible for returned receipts
          cy.contains("button", /pay now/i).should("not.exist");
        });
    });
  });

  describe("Checkout API Error Handling", () => {
    beforeEach(() => {
      cy.loginAsMember();
    });

    it("handles Stripe checkout API failure gracefully", () => {
      // Intercept checkout call and return an error
      cy.intercept("POST", `/api/receipts/*/stripe/checkout`, {
        statusCode: 400,
        body: {
          detail: "No active Stripe provider configured",
        },
      }).as("stripeCheckoutError");

      cy.visit("/en/my-receipts");

      // We need an emitted receipt to see the Pay Now button.
      // The receipt from the previous test block is returned, so
      // create a fresh one via API setup.
      // Instead, intercept the my-receipts list to include a payable receipt.
      cy.intercept("GET", "/api/members/me/receipts*", {
        statusCode: 200,
        body: {
          items: [
            {
              id: 9999,
              receipt_number: "REC-ERR-001",
              description: "Error handling test",
              base_amount: 25.0,
              vat_rate: 21,
              vat_amount: 5.25,
              total_amount: 30.25,
              status: "emitted",
              origin: "manual",
              emission_date: "2026-04-15",
              due_date: null,
              payment_date: null,
              payment_method: null,
              return_date: null,
              return_reason: null,
              discount_amount: null,
              discount_type: null,
              is_batchable: false,
              transaction_id: null,
              billing_period_start: null,
              billing_period_end: null,
              notes: null,
              is_active: true,
              created_at: null,
              updated_at: null,
              member_id: 1,
              concept_id: null,
              registration_id: null,
              remittance_id: null,
              created_by: null,
            },
          ],
          meta: { page: 1, per_page: 20, total: 1, total_pages: 1 },
        },
      }).as("myReceipts");

      cy.visit("/en/my-receipts");
      cy.wait("@myReceipts");
      cy.contains("Error handling test")
        .closest("tr")
        .find("button")
        .contains(/pay now/i)
        .click();

      cy.wait("@stripeCheckoutError");

      // Should show an error toast (global mutation error handler)
      cy.contains(/no active stripe provider|error/i).should("be.visible");
    });
  });
});
