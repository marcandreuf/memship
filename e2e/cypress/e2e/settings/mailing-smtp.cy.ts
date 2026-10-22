// Any SMTP server is configurable from the screen, with Gmail as a preset (#443).
// The mailing config is stubbed rather than written: it is global state, and a
// real write would overwrite whatever credentials the instance has on file.
const UNVERIFIED = {
  status: "unverified",
  last_success_at: null,
  last_failure_at: null,
  last_failure: null,
};

const MAILING_VIEW = {
  active_provider: null,
  resend: {
    from_email: "",
    api_key: { configured: false, last4: null },
    ready: false,
    health: UNVERIFIED,
  },
  smtp: {
    host: "",
    port: 587,
    tls: true,
    user: "",
    from_email: "",
    password: { configured: false, last4: null },
    ready: false,
    health: UNVERIFIED,
  },
  secrets_encryption_available: true,
  sources: { "smtp.port": "default", "smtp.tls": "default" },
};

const field = (label: string) => cy.contains("label", label).parent().find("input");

describe("SMTP mail provider", () => {
  beforeEach(() => {
    cy.intercept("GET", "/api/settings/mailing", MAILING_VIEW).as("mailing");
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.settingsTab("Integrations", "Mailing");
    cy.wait("@mailing");
  });

  it("saves a server of the association's own, with typed port and TLS", () => {
    cy.intercept("PUT", "/api/settings/mailing", (req) => req.reply(MAILING_VIEW)).as("save");
    field("Server").type("mail.club.example");
    field("Port").clear().type("2525");
    cy.get("#mailing-smtp-tls").click();
    field("SMTP user").type("secretaria@club.example");
    cy.contains("button", "Save").click();
    cy.wait("@save")
      .its("request.body")
      .should("deep.equal", {
        smtp: { host: "mail.club.example", port: 2525, tls: false, user: "secretaria@club.example" },
      });
  });

  it("fills in Gmail's endpoint from the preset", () => {
    cy.contains("button", "Use Gmail's settings").click();
    field("Server").should("have.value", "smtp.gmail.com");
    field("Port").should("have.value", "587");
    cy.get("#mailing-smtp-tls").should("have.attr", "aria-checked", "true");
  });

  it("does not label defaults as coming from the environment", () => {
    cy.contains("label", "Port").should("not.contain.text", "from environment");
  });

  it("refuses a port out of range before saving", () => {
    cy.intercept("PUT", "/api/settings/mailing", cy.spy().as("put"));
    field("Server").type("mail.club.example");
    field("Port").clear().type("70000");
    cy.contains("button", "Save").click();
    cy.contains("The port must be a number between 1 and 65535.").should("be.visible");
    cy.get("@put").should("not.have.been.called");
  });

  it("cannot be activated without a server and a sender", () => {
    cy.contains("button", "SMTP server").should("be.disabled");
    field("Server").type("mail.club.example");
    cy.contains("button", "SMTP server").should("be.disabled");
  });
});
