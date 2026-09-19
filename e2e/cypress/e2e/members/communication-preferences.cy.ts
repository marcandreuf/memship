// The member's own email opt-out, on the profile edit tab (#230). Before it,
// the preference had no write path at all — the column existed and the
// announcement audience read it, so the only way to set one was raw SQL.
//
// The switch saves on change rather than behind the Save button: that button
// posts to /members/me/profile, and this lives on the member record.

describe("Communication Preferences", () => {
  beforeEach(() => {
    cy.loginAsMember();
    cy.visit("/en/profile");
  });

  it("shows the club email toggle on the edit tab", () => {
    cy.contains(/receive club emails/i).should("be.visible");
  });

  it("says what the toggle does not cover", () => {
    // Account and billing mail keep arriving, and the copy has to say so —
    // the preference reads as a blanket "don't email me" otherwise.
    cy.contains(/account emails/i).should("be.visible");
    cy.contains(/billing emails/i).should("be.visible");
  });

  it("switches club email off and keeps it off across a reload", () => {
    cy.get('[data-testid="email-opt-in"]')
      .invoke("attr", "data-state")
      .then((initial) => {
        const flipped = initial === "checked" ? "unchecked" : "checked";

        cy.get('[data-testid="email-opt-in"]').click();
        cy.contains(/saved/i).should("be.visible");
        cy.get('[data-testid="email-opt-in"]').should(
          "have.attr",
          "data-state",
          flipped
        );

        cy.reload();
        cy.get('[data-testid="email-opt-in"]').should(
          "have.attr",
          "data-state",
          flipped
        );

        // Leave the seeded member as it was found — the suite shares it.
        cy.get('[data-testid="email-opt-in"]').click();
        cy.get('[data-testid="email-opt-in"]').should(
          "have.attr",
          "data-state",
          initial
        );
      });
  });
});
