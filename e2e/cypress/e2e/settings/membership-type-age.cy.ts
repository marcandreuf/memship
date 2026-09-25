// A membership type's age range could not be set from the UI, and nothing told
// an admin when a tier did not fit the member it was given (#291).
const API = Cypress.env("API_URL") || "http://localhost:8003/api/v1";

describe("Membership type — age range", () => {
  let typeName: string;
  let typeId: number;

  beforeEach(() => {
    cy.loginAsAdmin();
    // Inactive, so members' plan lists and the specs reading them never see
    // it. Types are only ever deactivated, never deleted, so each test makes
    // its own under a fresh slug.
    const stamp = Date.now();
    typeName = `Age Band ${stamp}`;
    cy.request("POST", `${API}/membership-types/`, {
      name: typeName,
      slug: `age-band-${stamp}`,
      is_active: false,
    }).then((r) => {
      typeId = r.body.id;
    });
  });

  function openEdit() {
    cy.visit("/en/settings");
    cy.settingsTab("Members", "Membership Types");
    cy.contains("tr", typeName).contains("button", "Edit").click();
  }

  it("sets and shows the age range", () => {
    openEdit();
    cy.get('[role="dialog"]').within(() => {
      cy.get('input[name="min_age"]').clear().type("16");
      cy.get('input[name="max_age"]').clear().type("25");
      cy.contains("button", "Save").click();
    });
    cy.contains(/saved successfully/i).should("be.visible");

    cy.contains("tr", typeName).should("contain.text", "16–25");
    cy.request(`${API}/membership-types/${typeId}`).then((r) => {
      expect([r.body.min_age, r.body.max_age]).to.deep.eq([16, 25]);
    });
  });

  it("refuses a maximum below the minimum", () => {
    openEdit();
    cy.get('[role="dialog"]').within(() => {
      cy.get('input[name="min_age"]').clear().type("30");
      cy.get('input[name="max_age"]').clear().type("20");
      cy.contains("button", "Save").click();
      cy.contains(/maximum must be greater than or equal/i).should("be.visible");
    });
  });
});

describe("Member form — tier outside its age range", () => {
  it("warns the admin but does not block", () => {
    cy.loginAsAdmin();
    cy.request("POST", `${API}/members/`, {
      first_name: "Adult",
      last_name: `Tier ${Date.now()}`,
      date_of_birth: "1980-01-01",
    }).then((r) => {
      cy.visit(`/en/members/${r.body.id}`);
    });
    cy.contains("button", "Edit").click();

    // Youth is seeded active with max_age 15.
    cy.contains("label", "Membership type").parent().find('[role="combobox"]').click();
    cy.contains('[role="option"]', "Youth").click();

    cy.get('[data-testid="type-age-warning"]')
      .should("contain.text", "capped at 15")
      .and("contain.text", "You can still assign it");
    cy.contains("button", "Save").should("be.enabled");
  });
});
