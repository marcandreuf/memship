// What credit-note.cy.ts does not cover (#163): where the button appears, where
// the browser goes after issuing, how the two documents point at each other,
// and how a credit note is told apart in the list.
//
// The member is resolved by exact email rather than by taking the first search
// hit: a substring search returns every account whose address contains the
// string, and the first of them is whichever the database happens to order
// first (#520).
describe("Receipts: credit note lifecycle", () => {
  const API_URL = Cypress.env("API_URL") || "http://localhost:8003/api/v1";
  const MEMBER_EMAIL = "member@examplee6e3b1.com";
  const ISSUE = "Emitir rectificativa";

  let partyId: number;

  // A receipt in the requested state, for the member resolved above.
  const createReceipt = (emit: boolean) =>
    cy
      .request({
        method: "POST",
        url: `${API_URL}/receipts`,
        body: {
          party_id: partyId,
          description: "Credit note lifecycle E2E receipt",
          base_amount: 100.0,
          vat_rate: 21,
          origin: "manual",
          emission_date: new Date().toISOString().slice(0, 10),
        },
      })
      .then((created) => {
        expect(created.status).to.eq(201);
        if (!emit) return created.body;
        return cy
          .request({ method: "POST", url: `${API_URL}/receipts/${created.body.id}/emit` })
          .then((emitted) => {
            expect(emitted.status).to.eq(200);
            return emitted.body;
          });
      });

  const creditInFull = (receiptId: number) =>
    cy
      .request({
        method: "POST",
        url: `${API_URL}/receipts/${receiptId}/credit-note`,
        body: { reason: "Credit note lifecycle E2E" },
      })
      .then((resp) => {
        expect(resp.status).to.eq(201);
        return resp.body;
      });

  beforeEach(() => {
    cy.apiLogin("admin@examplee6e3b1.com", "TestAdmin1!");
    cy.request({
      method: "GET",
      url: `${API_URL}/members?search=${encodeURIComponent(MEMBER_EMAIL)}&per_page=100`,
    }).then((resp) => {
      const member = resp.body.items.find(
        (m: { person?: { email?: string } }) => m.person?.email === MEMBER_EMAIL
      );
      expect(member, `member ${MEMBER_EMAIL}`).to.exist;
      partyId = member.party_id;
    });
  });

  describe("the button", () => {
    it("is not offered on a receipt that has not been issued", () => {
      createReceipt(false).then((receipt) => {
        cy.loginAsAdmin();
        cy.visit(`/es/receipts/${receipt.id}`);
        cy.contains("h1", receipt.receipt_number).should("be.visible");
        cy.contains("button", ISSUE).should("not.exist");
      });
    });

    it("is not offered once the receipt is credited in full", () => {
      createReceipt(true).then((receipt) => {
        creditInFull(receipt.id);
        cy.loginAsAdmin();
        cy.visit(`/es/receipts/${receipt.id}`);
        cy.contains("dt", "Importe rectificado").should("be.visible");
        cy.contains("button", ISSUE).should("not.exist");
      });
    });

    it("is not offered on a credit note itself", () => {
      createReceipt(true).then((receipt) => {
        creditInFull(receipt.id).then((note) => {
          cy.loginAsAdmin();
          cy.visit(`/es/receipts/${note.id}`);
          cy.contains("dt", "Rectifica").should("be.visible");
          cy.contains("button", ISSUE).should("not.exist");
        });
      });
    });
  });

  it("takes the admin to the new credit note, and each document names the other", () => {
    createReceipt(true).then((receipt) => {
      cy.intercept("POST", "/api/receipts/*/credit-note").as("createCreditNote");

      cy.loginAsAdmin();
      cy.visit(`/es/receipts/${receipt.id}`);
      cy.contains("button", ISSUE).click();
      cy.get('[role="dialog"]').within(() => {
        cy.get("input").first().type("Importe facturado de más");
        cy.contains("button", ISSUE).click();
      });

      cy.wait("@createCreditNote").then(({ response }) => {
        expect(response?.statusCode).to.eq(201);
        const note = response?.body;

        // The redirect, not just the API response: the page has to land on
        // the rectifying document.
        cy.location("pathname").should("eq", `/es/receipts/${note.id}`);
        cy.contains("h1", note.receipt_number).should("be.visible");
        cy.contains("dt", "Rectifica")
          .parent()
          .should("contain.text", receipt.receipt_number);

        // And the original now carries what was credited against it.
        cy.visit(`/es/receipts/${receipt.id}`);
        cy.contains("dt", "Importe rectificado").should("be.visible");
      });
    });
  });

  it("marks a credit note in the receipts list", () => {
    createReceipt(true).then((receipt) => {
      creditInFull(receipt.id).then((note) => {
        cy.loginAsAdmin();
        cy.visit(`/es/receipts?q=${encodeURIComponent(note.receipt_number)}`);
        cy.contains(note.receipt_number)
          .closest("tr, a")
          .should("contain.text", "Factura rectificativa");
      });
    });
  });
});
