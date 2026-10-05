// Stored credentials render as text with a Replace button, so a password
// manager has no input to fill and an untouched secret is never sent (#333).
// The mailing config is stubbed rather than written: it is global state, and a
// real write would overwrite whatever credentials the instance has on file.
const MAILING_VIEW = {
  active_provider: null,
  resend: {
    from_email: "",
    api_key: { configured: true, last4: "4f2a" },
    ready: true,
  },
  gmail: {
    user: "",
    from_email: "",
    app_password: { configured: false, last4: null },
    ready: false,
  },
  secrets_encryption_available: true,
  sources: {},
};

describe("Settings secret fields", () => {
  beforeEach(() => {
    cy.intercept("GET", "/api/settings/mailing", MAILING_VIEW).as("mailing");
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.settingsTab("Integrations", "Mailing");
    cy.wait("@mailing");
  });

  it("shows a stored secret as text, with no input to fill", () => {
    cy.get('[data-testid="mailing-resend-credential-stored"]')
      .should("contain.text", "•••• 4f2a")
      .and("contain.text", "stored");
    cy.get('input[name="mailing-resend-credential"]').should("not.exist");
  });

  it("reveals an empty input on Replace and hides it again on Cancel", () => {
    cy.get('[data-testid="mailing-resend-credential-stored"]')
      .parent()
      .contains("button", "Replace")
      .click();
    cy.get('input[name="mailing-resend-credential"]')
      .should("have.value", "")
      .and("have.attr", "autocomplete", "new-password");
    cy.contains("button", "Cancel").click();
    cy.get('input[name="mailing-resend-credential"]').should("not.exist");
    cy.get('[data-testid="mailing-resend-credential-stored"]').should("be.visible");
  });

  it("saving without Replace leaves the stored secret out of the payload", () => {
    cy.intercept("PUT", "/api/settings/mailing", (req) => {
      req.reply(MAILING_VIEW);
    }).as("save");
    cy.contains("label", "Gmail address").parent().find("input").type("club@example.org");
    cy.contains("button", "Save").click();
    cy.wait("@save").its("request.body").should((body) => {
      expect(body.gmail).to.deep.equal({ user: "club@example.org" });
      expect(body).not.to.have.property("resend");
    });
  });

  it("marks an unstored secret input as a new password", () => {
    cy.get('input[name="mailing-gmail-credential"]').should(
      "have.attr",
      "autocomplete",
      "new-password",
    );
  });
});
