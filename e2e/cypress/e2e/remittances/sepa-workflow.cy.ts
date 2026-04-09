describe("Remittance List", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/remittances");
  });

  it("shows remittance list page with title", () => {
    cy.contains("h1", /remittances/i).should("be.visible");
  });

  it("shows create remittance button", () => {
    cy.contains("button", /new remittance/i).should("be.visible");
  });

  it("shows status filter", () => {
    cy.get("button").contains(/status|all/i).should("be.visible");
  });

  it("opens create remittance dialog", () => {
    cy.contains("button", /new remittance/i).click();
    cy.contains(/select receipts|select emitted/i).should("be.visible");
  });
});

describe("Remittance Detail", () => {
  it("shows remittance detail when one exists", () => {
    cy.loginAsAdmin();
    cy.visit("/en/remittances");

    // Only test if there are remittances in the table
    cy.get("body").then(($body) => {
      if ($body.find("table tbody tr").length > 0) {
        cy.get("table tbody tr").first().click();
        cy.url().should("match", /\/remittances\/\d+/);
        cy.contains("REM-").should("be.visible");
        cy.contains(/draft|ready|submitted|processed|closed|cancelled/i).should("be.visible");
      }
    });
  });
});

describe("Remittance Access Control", () => {
  it("member cannot see remittances page", () => {
    cy.loginAsMember();
    cy.visit("/en/remittances");
    cy.contains("h1", /remittances/i).should("not.exist");
  });
});
