describe("Receipts — Issue a credit note", () => {
  const API_URL = Cypress.env("API_URL") || "http://localhost:8003/api/v1";
  let receiptId: number;
  let receiptNumber: string;

  beforeEach(() => {
    // A credit note needs an issued receipt to rectify, and one that has not
    // been credited already — the button hides once the credited total reaches
    // the receipt total. A fresh receipt per test keeps that headroom.
    cy.apiLogin("admin@examplee6e3b1.com", "TestAdmin1!");

    cy.request({
      method: "GET",
      url: `${API_URL}/members?search=member@examplee6e3b1.com`,
    }).then((membersResp) => {
      const member = membersResp.body.items[0];
      expect(member).to.exist;

      cy.request({
        method: "POST",
        url: `${API_URL}/receipts`,
        body: {
          member_id: member.id,
          description: "Credit note E2E test receipt",
          base_amount: 100.0,
          vat_rate: 21,
          origin: "manual",
          emission_date: new Date().toISOString().slice(0, 10),
        },
      }).then((createResp) => {
        expect(createResp.status).to.eq(201);
        receiptId = createResp.body.id;

        cy.request({
          method: "POST",
          url: `${API_URL}/receipts/${receiptId}/emit`,
        }).then((emitResp) => {
          expect(emitResp.status).to.eq(200);
          receiptNumber = emitResp.body.receipt_number;
        });
      });
    });
  });

  it("rectifies an issued receipt from the detail page", () => {
    // Asserting on the proxied path, not the API one. The defect in #326 was a
    // missing Next.js route handler: the API endpoint worked and its backend
    // tests passed, while the browser's POST 404'd before leaving the frontend.
    // Only a request that traverses the proxy can catch that.
    cy.intercept("POST", "/api/receipts/*/credit-note").as("createCreditNote");

    cy.loginAsAdmin();
    cy.visit(`/es/receipts/${receiptId}`);

    cy.contains("button", "Emitir rectificativa").click();

    cy.get('[role="dialog"]').within(() => {
      cy.contains(receiptNumber).should("be.visible");
      cy.get("input").first().type("Importe facturado de más");
      cy.contains("button", "Emitir rectificativa").click();
    });

    cy.wait("@createCreditNote").then(({ response }) => {
      expect(response?.statusCode).to.eq(201);
      expect(response?.body.document_type).to.eq("credit_note");
      expect(response?.body.rectifies_receipt_id).to.eq(receiptId);
      // The money moves the other way, so the total is negative.
      expect(Number(response?.body.total_amount)).to.be.lessThan(0);
    });
  });

  it("credits a partial amount when one is given", () => {
    cy.intercept("POST", "/api/receipts/*/credit-note").as("createCreditNote");

    cy.loginAsAdmin();
    cy.visit(`/es/receipts/${receiptId}`);

    cy.contains("button", "Emitir rectificativa").click();

    cy.get('[role="dialog"]').within(() => {
      cy.get("input").first().type("Rectificación parcial");
      cy.get("input").eq(1).type("25");
      cy.contains("button", "Emitir rectificativa").click();
    });

    cy.wait("@createCreditNote").then(({ response }) => {
      expect(response?.statusCode).to.eq(201);
      expect(Number(response?.body.total_amount)).to.eq(-25);
    });
  });

  it("will not submit without a reason", () => {
    cy.loginAsAdmin();
    cy.visit(`/es/receipts/${receiptId}`);

    cy.contains("button", "Emitir rectificativa").click();

    cy.get('[role="dialog"]').within(() => {
      cy.contains("button", "Emitir rectificativa").should("be.disabled");
    });
  });
});
