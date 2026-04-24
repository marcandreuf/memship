describe("Redsys — Happy Path @smoke", () => {
  const API_URL = Cypress.env("API_URL") || "http://localhost:8003/api/v1";
  let emittedReceiptId: number;
  let redsysProviderId: number | null = null;

  before(() => {
    // Ensure a Redsys test provider exists and is active; create an emitted receipt.
    cy.apiLogin("super@test.com", "TestSuper1!");

    cy.request({
      method: "GET",
      url: `${API_URL}/payment-providers/`,
    }).then((listResp) => {
      expect(listResp.status).to.eq(200);
      const existing = listResp.body.items.find(
        (p: { provider_type: string }) => p.provider_type === "redsys"
      );
      if (existing) {
        redsysProviderId = existing.id;
        // Ensure it's active
        if (existing.status === "disabled") {
          cy.request({
            method: "POST",
            url: `${API_URL}/payment-providers/${existing.id}/toggle`,
          });
        }
      } else {
        cy.request({
          method: "POST",
          url: `${API_URL}/payment-providers/`,
          body: {
            provider_type: "redsys",
            display_name: "Redsys Test",
            status: "test",
            config: {
              merchant_code: "100000001",
              terminal_id: "1",
              secret_key: "sq7HjrUOBfKmC576ILgskD5srU870gJ7",
              environment: "test",
              currency_code: "978",
            },
            is_default: false,
          },
        }).then((createProv) => {
          expect(createProv.status).to.eq(201);
          redsysProviderId = createProv.body.id;
        });
      }
    });

    cy.apiLogin("admin@test.com", "TestAdmin1!");

    cy.request({
      method: "GET",
      url: `${API_URL}/members?search=member@test.com`,
    }).then((membersResp) => {
      expect(membersResp.status).to.eq(200);
      const member = membersResp.body.items[0];
      expect(member).to.exist;

      cy.request({
        method: "POST",
        url: `${API_URL}/receipts`,
        body: {
          member_id: member.id,
          description: "Redsys E2E test receipt",
          base_amount: 40.0,
          vat_rate: 21,
          origin: "manual",
          emission_date: new Date().toISOString().slice(0, 10),
        },
      }).then((createResp) => {
        expect(createResp.status).to.eq(201);
        const receiptId = createResp.body.id;

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

  it("shows Redsys and Bizum buttons on an emitted receipt", () => {
    cy.visit("/en/my-receipts");
    cy.contains("h1", /my receipts/i).should("be.visible");
    cy.contains("Redsys E2E test receipt")
      .closest("tr")
      .within(() => {
        cy.get('button[aria-label="Card (Redsys)"]').should("be.visible");
        cy.get('button[aria-label="Pay with Bizum"]').should("be.visible");
      });
  });

  it("calls the initiate API and returns signed form params when Card is clicked", () => {
    cy.intercept("POST", "/api/receipts/*/redsys/initiate").as("initiate");

    cy.visit("/en/my-receipts");
    cy.contains("Redsys E2E test receipt")
      .closest("tr")
      .find('button[aria-label="Card (Redsys)"]')
      .click();

    cy.wait("@initiate").then((interception) => {
      expect(interception.response?.statusCode).to.eq(200);
      const body = interception.response?.body;
      expect(body.redirect_url).to.match(/\/sis\/realizarPago$/);
      expect(body.form_params).to.include.keys([
        "Ds_SignatureVersion",
        "Ds_MerchantParameters",
        "Ds_Signature",
      ]);
      expect(body.ds_order).to.have.length(12);
    });
  });

  it("Bizum button passes method=bizum and marks receipt payment_method", () => {
    cy.intercept("POST", "/api/receipts/*/redsys/initiate").as("initiateBizum");

    cy.visit("/en/my-receipts");
    cy.contains("Redsys E2E test receipt")
      .closest("tr")
      .find('button[aria-label="Pay with Bizum"]')
      .click();

    cy.wait("@initiateBizum").then((interception) => {
      expect(interception.response?.statusCode).to.eq(200);
      expect(JSON.parse(String(interception.request.body)).method).to.eq("bizum");
    });

    // Receipt should now have payment_method='bizum' even before webhook
    cy.apiLogin("admin@test.com", "TestAdmin1!");
    cy.request({
      method: "GET",
      url: `${API_URL}/receipts/${emittedReceiptId}`,
    }).then((resp) => {
      expect(resp.status).to.eq(200);
      expect(resp.body.payment_method).to.eq("bizum");
    });
  });

  it("return page shows paid state after backend marks the receipt paid", () => {
    // Simulate the async notification via admin pay endpoint.
    cy.apiLogin("admin@test.com", "TestAdmin1!");
    cy.request({
      method: "POST",
      url: `${API_URL}/receipts/${emittedReceiptId}/pay`,
      body: {
        payment_method: "redsys",
        payment_date: new Date().toISOString().split("T")[0],
      },
    }).then((payResp) => {
      expect(payResp.status).to.eq(200);
      expect(payResp.body.status).to.eq("paid");
    });

    cy.loginAsMember();
    cy.visit(
      `/en/payment/redsys/return?receipt_id=${emittedReceiptId}&outcome=ok`
    );
    cy.contains(/payment.*success|payment.*confirmed/i, { timeout: 10000 }).should(
      "be.visible"
    );
    cy.contains("button", /back to my receipts/i).should("be.visible");
  });

  it("my receipts shows paid status and hides Redsys buttons", () => {
    cy.visit("/en/my-receipts");
    cy.contains("Redsys E2E test receipt")
      .closest("tr")
      .within(() => {
        cy.contains(/paid/i).should("be.visible");
        cy.get('button[aria-label="Card (Redsys)"]').should("not.exist");
        cy.get('button[aria-label="Pay with Bizum"]').should("not.exist");
      });
  });
});


describe("Redsys — Visibility gate @smoke", () => {
  const API_URL = Cypress.env("API_URL") || "http://localhost:8003/api/v1";

  it("hides Redsys buttons when no active Redsys provider is configured", () => {
    // Ensure no active Redsys provider: disable if present.
    cy.apiLogin("super@test.com", "TestSuper1!");
    cy.request({
      method: "GET",
      url: `${API_URL}/payment-providers/`,
    }).then((listResp) => {
      const redsys = listResp.body.items.find(
        (p: { provider_type: string }) => p.provider_type === "redsys"
      );
      if (redsys && redsys.status !== "disabled") {
        cy.request({
          method: "POST",
          url: `${API_URL}/payment-providers/${redsys.id}/toggle`,
        });
      }
    });

    cy.loginAsMember();
    cy.visit("/en/my-receipts");
    cy.get("body").then(($body) => {
      if ($body.find("tr").length > 1) {
        cy.get("tr")
          .not(":first")
          .first()
          .within(() => {
            cy.get('button[aria-label="Card (Redsys)"]').should("not.exist");
            cy.get('button[aria-label="Pay with Bizum"]').should("not.exist");
          });
      }
    });

    // Re-enable for subsequent runs
    cy.apiLogin("super@test.com", "TestSuper1!");
    cy.request({
      method: "GET",
      url: `${API_URL}/payment-providers/`,
    }).then((listResp) => {
      const redsys = listResp.body.items.find(
        (p: { provider_type: string }) => p.provider_type === "redsys"
      );
      if (redsys && redsys.status === "disabled") {
        cy.request({
          method: "POST",
          url: `${API_URL}/payment-providers/${redsys.id}/toggle`,
        });
      }
    });
  });
});
