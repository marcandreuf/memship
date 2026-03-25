// =============================================================================
// E2E Tests — Section 8: Eligibility Rules
// =============================================================================
//
// Seed member statuses (verified from DB):
//   nuria@test.com    — active, DOB 1983-12-02 (age ~42), 0 registrations
//   member@test.com   — active, no DOB, 6 registrations
//   david@test.com    — pending
//   montse@test.com   — suspended
//   ferran@test.com   — expired
//
// Seed activities with restrictions:
//   Kids Dance Party          — max_age: 12
//   Summer Soccer Camp        — min_age: 6, max_age: 17
//   Chess Club Tournament     — no age restriction, open registration
//   Spring Marathon 2026      — registration closed
//   New Year's Gala 2027      — registration not yet open
//   Yoga Workshop             — no restrictions, open registration

const PASSWORD = "TestMember1!";

/**
 * Navigate to an activity's registration page by extracting href
 * from the activity card and visiting /register directly.
 */
function visitRegisterPage(activityName: string) {
  cy.visit("/en/activities");
  cy.contains("h3", activityName)
    .closest("a")
    .invoke("attr", "href")
    .then((href) => {
      cy.visit(`${href}/register`);
      cy.url().should("include", "/register");
    });
}

/**
 * Navigate to an activity detail page from the list.
 */
function visitActivityDetail(activityName: string) {
  cy.visit("/en/activities");
  cy.contains("h3", activityName).closest("a").click();
  cy.url().should("match", /\/activities\/\d+/);
}

describe("8. Eligibility Rules — Age Restrictions", () => {
  // Using nuria@test.com — active, DOB 1983, age ~42, 0 registrations
  it("8.1 — adult rejected from kids-only activity (max_age=12)", () => {
    cy.login("nuria@test.com", PASSWORD);
    visitRegisterPage("Kids Dance Party");

    cy.contains("You are not eligible").should("be.visible");
    cy.contains("Maximum age is 12").should("be.visible");
  });

  it("8.2 — adult rejected from youth activity (max_age=17)", () => {
    cy.login("nuria@test.com", PASSWORD);
    visitRegisterPage("Summer Soccer Camp");

    cy.contains("You are not eligible").should("be.visible");
    cy.contains("Maximum age is 17").should("be.visible");
  });

  // Using member@test.com — active, no DOB (age checks skipped), has available activities
  it("8.3 — eligible member can access registration form", () => {
    cy.login("member@test.com", PASSWORD);
    visitRegisterPage("Chess Club Tournament");

    cy.contains("You are eligible").should("be.visible");
    cy.contains("You are not eligible").should("not.exist");
  });
});

describe("8. Eligibility Rules — Member Status", () => {
  it("8.7a — pending member is not eligible", () => {
    cy.login("david@test.com", PASSWORD);
    visitRegisterPage("Yoga Workshop");

    cy.contains("You are not eligible").should("be.visible");
    cy.contains("Member status is not active").should("be.visible");
  });

  it("8.7b — suspended member is not eligible", () => {
    cy.login("montse@test.com", PASSWORD);
    visitRegisterPage("Yoga Workshop");

    cy.contains("You are not eligible").should("be.visible");
    cy.contains("Member status is not active").should("be.visible");
  });

  it("8.7c — expired member is not eligible", () => {
    cy.login("ferran@test.com", PASSWORD);
    visitRegisterPage("Yoga Workshop");

    cy.contains("You are not eligible").should("be.visible");
    cy.contains("Member status is not active").should("be.visible");
  });
});

describe("8. Eligibility Rules — Registration Window", () => {
  it("8.6a — closed registration shows Closed badge", () => {
    cy.login("nuria@test.com", PASSWORD);
    visitActivityDetail("Spring Marathon 2026");

    cy.contains(/closed/i).should("be.visible");
  });

  it("8.6b — not-yet-open registration shows Not Yet Open badge", () => {
    cy.login("nuria@test.com", PASSWORD);
    visitActivityDetail("New Year's Gala 2027");

    cy.contains(/not yet open/i).should("be.visible");
  });
});

describe("8. Eligibility Rules — Duplicate Registration", () => {
  it("8.5 — already registered member sees Registered status", () => {
    cy.login("member@test.com", PASSWORD);

    cy.visit("/en/my-activities");
    cy.get("a[href*='/activities/']").should("have.length.greaterThan", 0);

    cy.get("a[href*='/activities/']").first().click();
    cy.url().should("match", /\/activities\/\d+/);

    cy.contains(/confirmed|waitlisted|registered/i).should("be.visible");
  });
});
