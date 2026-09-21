// A failed mutation whose body is `{"detail": {"code": …}}` and nothing else
// used to toast the literal "Validation error" (before #256) and then the bare
// code (after it). The global handler now renders `apiErrors.<code>` when a
// translation exists and the generic error text when none does (#263).
//
// Stubbed rather than provoked: `forbidden` comes from `require_permission`,
// and no seeded account can reach a form it is then refused on.

describe("Coded error toasts", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/spaces");
    cy.contains("button", "New space").click();
    cy.get('[role="dialog"]').within(() => {
      cy.get('input[name="name"]').type(`Refused ${Date.now()}`);
    });
  });

  function submit() {
    cy.get('[role="dialog"] button[type="submit"]').click();
  }

  it("translates a code the UI knows", () => {
    cy.intercept("POST", "/api/spaces", {
      statusCode: 403,
      body: { detail: { code: "forbidden", required: "bookings.write" } },
    }).as("refused");
    submit();
    cy.wait("@refused");
    cy.get("[data-sonner-toast]").should(
      "contain.text",
      "You don't have permission to do this"
    );
  });

  it("falls back to the generic text for a code it does not know", () => {
    cy.intercept("POST", "/api/spaces", {
      statusCode: 409,
      body: { detail: { code: "something_new_the_ui_has_not_met" } },
    }).as("refused");
    submit();
    cy.wait("@refused");
    cy.get("[data-sonner-toast]")
      .should("contain.text", "Something went wrong")
      .and("not.contain.text", "something_new_the_ui_has_not_met");
  });
});

export {};
