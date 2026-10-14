describe("Mandate List", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/mandates");
  });

  it("shows mandate list page with title", () => {
    cy.contains("h1", /mandates/i).should("be.visible");
  });

  it("shows create mandate button", () => {
    cy.contains("button", /new mandate/i).should("be.visible");
  });

  it("shows mandate table with seeded data", () => {
    cy.get("table tbody tr").should("have.length.greaterThan", 0);
  });

  it("filters mandates by status", () => {
    // Open status filter select trigger
    cy.get('[data-slot="select-trigger"]').click();
    cy.contains('[data-slot="select-item"]', "Active").click();
    cy.get("table tbody tr").should("have.length.greaterThan", 0);
  });

  it("searches mandates by name", () => {
    cy.get('input[placeholder*="Search"]').type("María");
    cy.contains("María").should("be.visible");
  });

  it("navigates to mandate detail on row click", () => {
    cy.get("table tbody tr").first().click();
    cy.url().should("match", /\/mandates\/\d+/);
  });
});

describe("Mandate Detail", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/mandates");
    cy.get("table tbody tr").first().click();
    cy.url().should("match", /\/mandates\/\d+/);
  });

  it("shows mandate detail with reference and status", () => {
    cy.contains("FAC-").should("be.visible");
    cy.contains(/active|cancelled/i).should("be.visible");
  });

  it("shows download PDF link", () => {
    cy.contains("a", /download pdf/i).should("be.visible");
  });

  it("shows signed document status", () => {
    cy.contains(/signed document|no signed document/i).should("be.visible");
  });
});

describe("Mandate Access Control", () => {
  it("member cannot see mandates page", () => {
    cy.loginAsMember();
    cy.visit("/en/mandates");
    cy.contains("h1", /mandates/i).should("not.exist");
  });
});

// A failed mandate save used to be answered with "Something went wrong" — the
// `catch` did not bind the error, so the server's reason was discarded at the
// boundary (#355). This is the sharpest instance of that: #344 made a
// bad-checksum IBAN a 422 with a field-level reason, and this screen was the
// one throwing it away.
//
// Stubbed rather than provoked, as in validation/coded-error-toast.cy.ts: the
// backend already has tests for producing the 422, and what is under test here
// is the screen surfacing it.
describe("Mandate save errors reach the admin", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/mandates");
    cy.contains("button", /new mandate/i).click();
    cy.get('[role="dialog"]').within(() => {
      cy.get('input[type="number"]').type("1");
      cy.get("input").eq(1).type("Checksum Test");
      cy.get('input[placeholder="ES9121000418450200051332"]').type(
        "ES9121000418450200051333"
      );
    });
  });

  function submit() {
    cy.get('[role="dialog"] button[type="submit"]').click();
  }

  it("shows the field-level reason a 422 carries", () => {
    cy.intercept("POST", "/api/mandates", {
      statusCode: 422,
      body: {
        detail: [
          {
            loc: ["body", "debtor_iban"],
            msg: "Value error, Invalid IBAN",
            type: "value_error",
          },
        ],
      },
    }).as("refused");
    submit();
    cy.wait("@refused");
    cy.get("[data-sonner-toast]")
      .should("contain.text", "Invalid IBAN")
      .and("not.contain.text", "Something went wrong");
  });

  // Binding the error is only an improvement if there is always something to
  // show. `client-api` falls back to `res.statusText` for a body with no
  // `detail`, and HTTP/2 dropped the reason phrase — so behind Caddy that is
  // the empty string. An empty message is a toast sonner does not render at
  // all, which would turn a failed save into silence: worse than the generic
  // text this PR replaced. An empty `detail` reproduces that deterministically,
  // without depending on what statusText a given server or stub supplies.
  it("still shows the generic text when the error carries no reason", () => {
    cy.intercept("POST", "/api/mandates", {
      statusCode: 500,
      body: { detail: "" },
    }).as("broke");
    submit();
    cy.wait("@broke");
    cy.get("[data-sonner-toast]").should("contain.text", "Something went wrong");
  });
});

