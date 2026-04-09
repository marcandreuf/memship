describe("Payment Method Page", () => {
  beforeEach(() => {
    cy.loginAsMember();
    cy.visit("/en/payment-method");
  });

  it("shows payment method page with title", () => {
    cy.contains("h1", /payment method/i).should("be.visible");
  });

  it("shows payment method options", () => {
    cy.contains(/direct debit/i).should("be.visible");
    cy.contains(/bank transfer/i).should("be.visible");
    cy.contains(/cash/i).should("be.visible");
    cy.contains(/card/i).should("be.visible");
  });

  it("selects a payment method and shows save button", () => {
    cy.contains(/bank transfer/i).click();
    cy.contains("button", /save/i).should("be.visible");
  });

  it("shows bank details when direct debit selected", () => {
    cy.contains(/direct debit/i).click();
    cy.contains(/iban/i).should("be.visible");
    cy.contains(/bic/i).should("be.visible");
    cy.contains(/account holder/i).should("be.visible");
  });

  it("shows mandate info when direct debit selected", () => {
    cy.contains(/direct debit/i).click();
    // Member may or may not have a mandate, both states are valid
    cy.get("body").then(($body) => {
      const hasMandate = $body.text().includes("FAC-");
      if (hasMandate) {
        cy.contains(/mandate reference/i).should("be.visible");
      } else {
        cy.contains(/no mandate|none/i).should("be.visible");
      }
    });
  });
});

describe("Payment Method — Member with Mandate", () => {
  it("shows mandate info for maria (has active mandate)", () => {
    cy.login("maria@test.com", "TestMember1!");
    cy.visit("/en/payment-method");
    cy.contains(/direct debit/i).click();
    cy.contains("FAC-").should("be.visible");
    cy.contains(/active/i).should("be.visible");
  });
});

describe("Payment Method — Access Control", () => {
  it("payment method link visible in member sidebar", () => {
    cy.loginAsMember();
    cy.contains(/payment method/i).should("be.visible");
  });

  it("payment method link not visible in admin sidebar", () => {
    cy.loginAsAdmin();
    cy.contains("a", /payment method/i).should("not.exist");
  });
});
