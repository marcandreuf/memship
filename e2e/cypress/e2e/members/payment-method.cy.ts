// Payment method lives as a tab on the profile page; the old /payment-method
// URL redirects there (with the tab preselected) for bookmarks.

describe("Payment Method Tab", () => {
  beforeEach(() => {
    cy.loginAsMember();
    cy.visit("/en/payment-method");
  });

  it("old URL redirects to the profile payment tab", () => {
    cy.url().should("include", "/profile");
    cy.contains('[role="tab"]', /payment method/i)
      .should("have.attr", "data-state", "active");
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
    cy.login("maria@examplee6e3b1.com", "TestMember1!");
    cy.visit("/en/payment-method");
    cy.contains(/direct debit/i).click();
    cy.contains("FAC-").should("be.visible");
    cy.contains(/active/i).should("be.visible");
  });
});

describe("Payment Method — Navigation", () => {
  it("has no sidebar entry; reachable via the profile tabs", () => {
    cy.loginAsMember();
    cy.visit("/en/dashboard");
    cy.contains("a", /payment method/i).should("not.exist");
    cy.visit("/en/profile");
    cy.contains('[role="tab"]', /payment method/i).click();
    cy.contains(/direct debit/i).should("be.visible");
  });

  it("payment method not visible in admin sidebar", () => {
    cy.loginAsAdmin();
    cy.contains("a", /payment method/i).should("not.exist");
  });
});
