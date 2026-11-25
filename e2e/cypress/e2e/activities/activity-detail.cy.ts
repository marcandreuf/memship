describe("Activity Detail — Admin", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/activities");
    cy.get('input[placeholder*="Search"]').type("Soccer");
    cy.contains("Summer Soccer Camp").click();
    cy.url().should("match", /\/activities\/\d+/);
  });

  it("shows breadcrumbs", () => {
    cy.get("nav[aria-label='breadcrumb']").within(() => {
      cy.contains("Activities").should("be.visible");
      cy.contains("Summer Soccer Camp").should("be.visible");
    });
  });

  it("shows activity name and status badge", () => {
    cy.contains("h1", "Summer Soccer Camp").should("be.visible");
    cy.contains(/published/i).should("be.visible");
  });

  it("shows basic information section", () => {
    cy.contains("Basic Information").should("be.visible");
    cy.contains("Main Stadium").should("be.visible");
  });

  it("shows all entity tabs", () => {
    cy.contains("button", "Modalities").should("be.visible");
    cy.contains("button", "Prices").should("be.visible");
    cy.contains("button", "Registrations").should("be.visible");
    cy.contains("button", "Discounts").should("be.visible");
    cy.contains("button", "Consents").should("be.visible");
    cy.contains("button", "Attachments").should("be.visible");
  });

  it("shows modalities tab with data", () => {
    cy.contains("button", "Modalities").click();
    cy.contains("Morning Only").should("be.visible");
    cy.contains("Full Day").should("be.visible");
  });

  it("shows prices tab with data", () => {
    cy.contains("button", "Prices").click();
    cy.contains("Early Bird").should("be.visible");
    cy.contains("General").should("be.visible");
  });

  it("shows registrations tab with data", () => {
    cy.contains("button", "Registrations").click();
    cy.get("table").should("be.visible");
  });

  it("shows lifecycle action buttons", () => {
    cy.contains("button", /archive/i).should("be.visible");
    cy.contains("button", /cancel/i).should("be.visible");
  });

  it("has edit button for basic info", () => {
    cy.contains("button", "Edit").should("be.visible");
  });
});

// =============================================================================
// #590 — the member's Register control sits in the header, not behind a tab
// =============================================================================
//
// Seed pairs this relies on, verified against the dev database:
//   nuria@examplee6e3b1.com  — active, no registrations
//   member@examplee6e3b1.com — confirmed on Yoga Workshop, cancelled on
//                              Private Wine Tasting
//   Chess Club Tournament    — published, registration open
//   Spring Marathon 2026     — published, registration closed
//
// Activity ids are seed-dependent, so each test reaches the detail page through
// the name-filtered list rather than a hardcoded id.

const MEMBER_PASSWORD = "TestMember1!";

function openActivityAsMember(name: string) {
  cy.visit(`/en/activities?q=${encodeURIComponent(name)}`);
  cy.contains("h3", name).closest("a").click();
  cy.url().should("match", /\/activities\/\d+/);
}

// Anything inside the Tabs root is behind a tab — which is what #590 asked for
// the Register control to come out of. `[role="tab"]` and anchored regexes
// follow members/detail-tab-in-url.cy.ts: "Register" is a prefix of
// "Registered", so a substring match would pass on the wrong element.
const tabsRoot = () => cy.get('[data-slot="tabs"]');
const registerLink = () => cy.get('a[href$="/register"]');

describe("Activity Detail — member Register control (#590)", () => {
  it("offers Register in the header, with no tab to open first", () => {
    cy.login("nuria@examplee6e3b1.com", MEMBER_PASSWORD);
    openActivityAsMember("Chess Club Tournament");

    registerLink().should("be.visible");
    tabsRoot().find('a[href$="/register"]').should("not.exist");
    cy.contains('[role="tab"]', /^Register$/).should("not.exist");
  });

  it("navigates to the registration form from the header", () => {
    cy.login("nuria@examplee6e3b1.com", MEMBER_PASSWORD);
    openActivityAsMember("Chess Club Tournament");

    registerLink().click();
    cy.url().should("match", /\/activities\/\d+\/register/);
  });

  it("shows the header control disabled when registration is closed", () => {
    cy.login("nuria@examplee6e3b1.com", MEMBER_PASSWORD);
    openActivityAsMember("Spring Marathon 2026");

    cy.contains("button", /^Register$/).should("be.visible").and("be.disabled");
    registerLink().should("not.exist");
  });

  it("gives an already-registered member no second way to register", () => {
    cy.loginAsMember();
    openActivityAsMember("Yoga Workshop");

    cy.contains("a", "View my registration").should("be.visible");
    cy.contains("button", /^Register$/).should("not.exist");
    registerLink().should("not.exist");
  });

  it("keeps the registration card reachable, from the header and the tab", () => {
    cy.loginAsMember();
    openActivityAsMember("Yoga Workshop");

    // The header control opens the tab that holds the card.
    cy.contains("a", "View my registration").click();
    cy.contains(/you are already registered/i).should("be.visible");

    // And the tab itself is still there to be clicked.
    cy.contains('[role="tab"]', /^Registered$/).click();
    cy.contains(/you are already registered/i).should("be.visible");
  });

  it("lets a cancelled member register again while the card still shows", () => {
    cy.loginAsMember();
    openActivityAsMember("Private Wine Tasting");

    registerLink().should("be.visible");
    cy.contains('[role="tab"]', /^Cancelled$/).click();
    cy.contains('[role="tabpanel"]', /cancelled/i).should("be.visible");
  });
});
