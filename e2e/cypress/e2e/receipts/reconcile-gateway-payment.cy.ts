// Recording by hand a payment the gateway took but whose notification never
// applied: the true method, plus the gateway's reference (#426).
describe("Receipts — reconcile a gateway payment", () => {
  const API_URL = Cypress.env("API_URL") || "http://localhost:8003/api/v1";
  // The seeded member these specs raise a receipt against, matched exactly
  // below rather than by position in a substring search (#520).
  const MEMBER_EMAIL = "member@examplee6e3b1.com";
  const reference = `E2E${Date.now().toString().slice(-6)}`;
  let receiptId: number;

  before(() => {
    cy.apiLogin("admin@examplee6e3b1.com", "TestAdmin1!");
    cy.request(`${API_URL}/members?search=${MEMBER_EMAIL}`).then((members) => {
      // Match the address, do not trust the position: `search` is a substring
      // match, so any account whose address merely *contains* this one comes
      // back too and `items[0]` picks whichever sorts first (#520).
      const member = members.body.items.find(
        (m) => m.person.email === MEMBER_EMAIL
      );
      expect(member, `the seeded member test account ${MEMBER_EMAIL}`).to.exist;
      cy.request("POST", `${API_URL}/receipts`, {
        party_id: member.party_id,
        description: "Reconcile E2E receipt",
        base_amount: 30.0,
        vat_rate: 0,
        origin: "manual",
        emission_date: new Date().toISOString().slice(0, 10),
      }).then((created) => {
        receiptId = created.body.id;
        cy.request("POST", `${API_URL}/receipts/${receiptId}/emit`);
      });
    });
  });

  beforeEach(() => {
    cy.loginAsAdmin();
  });

  it("asks for the gateway reference and records it with the payment", () => {
    cy.visit(`/en/receipts/${receiptId}`);
    cy.contains("button", "Mark Paid").click();

    cy.get("[role='dialog']").within(() => {
      cy.get("[role='combobox']").click();
    });
    cy.contains("[role='option']", "Redsys").click();

    cy.get("[role='dialog']").within(() => {
      cy.contains("label", "Gateway reference").should("be.visible");
      cy.contains("button", "Mark Paid").should("be.disabled");
      cy.get("#gateway-reference").type(reference);
      cy.contains("button", "Mark Paid").should("not.be.disabled").click();
    });

    cy.get("[role='dialog']").should("not.exist");
    cy.contains("Gateway reference").parent().should("contain", reference);
    cy.request(`${API_URL}/receipts/${receiptId}`).then((resp) => {
      expect(resp.body.status).to.eq("paid");
      expect(resp.body.payment_method).to.eq("redsys");
      expect(resp.body.transaction_id).to.eq(reference);
    });
  });
});
