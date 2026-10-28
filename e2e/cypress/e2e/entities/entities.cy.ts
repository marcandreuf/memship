// Entities: non-member parties (companies, foundations, public bodies) an
// admin registers so money can be addressed to them — the donation flow.
// Phase 5b of the party refactor. Mutates nothing in organization_settings,
// so it runs in the general pool.

function uniqueName(prefix: string) {
  return `${prefix} ${Date.now()}-${Cypress._.random(1000, 9999)}`;
}

function createEntity(name: string) {
  cy.visit("/en/entities");
  cy.contains("button", /new entity/i).click();
  cy.url().should("include", "/entities/new");
  cy.get("form").within(() => {
    cy.get("input").eq(0).type(name);
    cy.get('input[placeholder="B12345678"]').type("B29045673");
    cy.get('input[type="email"]').type(`e2e-${Date.now()}@example.org`);
    cy.contains("button", /save/i).click();
  });
  cy.url().should("match", /\/entities\/\d+/);
  cy.contains("h1", name).should("be.visible");
}

describe("Entity list", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
  });

  it("shows the list page with title and create button", () => {
    cy.visit("/en/entities");
    cy.contains("h1", /entities/i).should("be.visible");
    cy.contains("button", /new entity/i).should("be.visible");
  });

  it("creates an entity and finds it by search", () => {
    const name = uniqueName("Search Target SL");
    createEntity(name);

    cy.visit("/en/entities");
    cy.get('input[placeholder*="Search"]').type(name);
    // Assert visibility only: clicking right after typing races the debounced
    // search-param URL write, which can flush after the row navigation and
    // bounce back to the list. Row-click navigation is covered below, without
    // a pending search update in flight.
    cy.contains("td", name).should("be.visible");
  });

  it("navigates to entity detail on row click", () => {
    createEntity(uniqueName("Clickable SL"));
    cy.visit("/en/entities");
    cy.get("table tbody tr").first().click();
    cy.url().should("match", /\/entities\/\d+/);
  });
});

describe("Entity detail", () => {
  beforeEach(() => {
    cy.loginAsAdmin();
  });

  it("edits the entity in place", () => {
    const name = uniqueName("Editable SL");
    const renamed = uniqueName("Renamed SL");
    createEntity(name);

    cy.contains("button", /^edit$/i).click();
    cy.get("form").within(() => {
      cy.get("input").eq(0).clear().type(renamed);
      cy.contains("button", /save/i).click();
    });
    cy.contains("[data-sonner-toast]", /saved/i).should("be.visible");
    cy.contains("h1", renamed).should("be.visible");
  });

  it("adds an address and a contact", () => {
    createEntity(uniqueName("Con Sede SL"));

    cy.contains('[role="tab"]', /address/i).click();
    cy.contains("button", /add address/i).click();
    cy.get("form").within(() => {
      cy.get("input").eq(0).type("Calle Mayor 1");
      cy.get("input").eq(2).type("Madrid");
      cy.contains("button", /save/i).click();
    });
    cy.contains("[data-sonner-toast]", /saved/i).should("be.visible");
    cy.contains("Calle Mayor 1").should("be.visible");

    cy.contains('[role="tab"]', /contacts/i).click();
    cy.contains("button", /add contact/i).click();
    cy.get('[role="dialog"]').within(() => {
      cy.get('input[placeholder*="600"]').type("+34 910 000 001");
      cy.contains("button", /save/i).click();
    });
    cy.contains("[data-sonner-toast]", /saved/i).should("be.visible");
    cy.contains("+34 910 000 001").should("be.visible");
  });

  it("records a donation receipt and then refuses to delete the entity", () => {
    createEntity(uniqueName("Donante SL"));

    cy.contains('[role="tab"]', /receipts/i).click();
    cy.contains("button", /new receipt/i).click();
    cy.get('[role="dialog"]').within(() => {
      cy.contains("label", /description/i)
        .parent()
        .find("input")
        .type("Donación anual");
      cy.contains("label", /base/i).parent().find("input").clear().type("500");
      cy.contains("button", /save/i).click();
    });
    cy.contains("[data-sonner-toast]", /saved/i).should("be.visible");
    cy.contains("td", "Donación anual").should("be.visible");

    // Money outlives everything: the delete is refused with a reason
    cy.contains("button", /^delete$/i).click();
    cy.get('[role="alertdialog"]').contains("button", /delete/i).click();
    cy.contains("[data-sonner-toast]", /cannot delete/i).should("be.visible");
    cy.contains("h1", "Donante SL").should("be.visible");
  });

  it("deletes an entity without history", () => {
    const name = uniqueName("Efímera SL");
    createEntity(name);

    cy.contains("button", /^delete$/i).click();
    cy.get('[role="alertdialog"]').contains("button", /delete/i).click();
    cy.contains("[data-sonner-toast]", /deleted/i).should("be.visible");
    cy.url().should("match", /\/entities$/);
  });
});

describe("Entity access control", () => {
  it("member sees neither the nav entry nor the page", () => {
    cy.loginAsMember();
    cy.visit("/en/dashboard");
    cy.contains("a", /entities/i).should("not.exist");
    cy.visit("/en/entities");
    cy.contains("h1", /entities/i).should("not.exist");
  });

  it("treasurer (billing-only role) cannot open entities but can search parties", () => {
    cy.loginAsTreasurer();
    cy.visit("/en/entities");
    cy.contains("h1", /entities/i).should("not.exist");

    // The mandate form's party picker rides on billing.read
    cy.visit("/en/mandates");
    cy.contains("button", /new mandate/i).click();
    cy.get('[role="dialog"]').within(() => {
      cy.get('input[placeholder*="Search by name"]').type("María");
    });
    cy.get('[role="dialog"]').contains("button", "María").should("be.visible");
  });
});
