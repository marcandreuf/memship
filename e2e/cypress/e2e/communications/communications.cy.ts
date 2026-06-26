// =============================================================================
// Communications (v0.5.0) — admin compose/send, member notifications, RBAC
// =============================================================================

const SUBJECT = "E2E Broadcast Announcement";

describe("Communications (v0.5.0)", () => {
  before(() => {
    // Enable the module (persists in org settings) so nav, bell, and the
    // member announcements page are available for the rest of the suite.
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.contains('[role="tab"]', "Communications").click();
    cy.get('[role="switch"]').then(($sw) => {
      if ($sw.attr("aria-checked") !== "true") cy.wrap($sw).click();
    });
    cy.get('[role="switch"]').should("have.attr", "aria-checked", "true");
    cy.contains("button", "Save").click();
    cy.contains(/saved successfully/i).should("be.visible");
  });

  it("shows the Communications settings toggle (super admin)", () => {
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.contains('[role="tab"]', "Communications").click();
    cy.contains("Enable communications").should("be.visible");
    cy.contains("button", "Save").should("be.visible");
  });

  it("composes a draft, previews the audience, and sends it", () => {
    cy.loginAsAdmin();
    cy.visit("/en/communications/new");

    cy.get('input[maxlength="200"]').type(SUBJECT);
    cy.get("textarea").type("Hello **everyone** — this is an end-to-end test.");
    // Target defaults to "All members".
    cy.contains("button", "Save draft").click();

    // Saving a draft routes to its page, where audience preview + Send appear.
    cy.url().should("match", /\/communications\/\d+$/);
    cy.contains(/members will receive this announcement/i).should("be.visible");

    cy.contains("button", "Send").click();
    cy.get('[role="dialog"]').within(() => {
      cy.contains(/send announcement\?/i).should("be.visible");
      cy.contains("button", "Send").click();
    });

    // Back to history, listed as sent.
    cy.url().should("match", /\/communications$/);
    cy.contains("td", SUBJECT).should("be.visible");
    cy.contains("Sent").should("be.visible");
  });

  it("delivers an in-app notification and mark-all-read clears the badge", () => {
    cy.loginAsMember();
    cy.visit("/en/dashboard");

    cy.get('header button[aria-label="Notifications"]').click();
    cy.contains(SUBJECT).should("be.visible");
    // "Mark all read" only renders while the unread count > 0; clicking it must
    // drive the count to 0, which removes the control. Asserting it disappears
    // verifies the badge cleared without leaving the open dropdown.
    cy.contains("button", "Mark all read").click();
    cy.contains("button", "Mark all read").should("not.exist");
  });

  it("lists received announcements on the member page", () => {
    cy.loginAsMember();
    cy.visit("/en/announcements");
    cy.contains(SUBJECT).should("be.visible");
    // Markdown body rendered.
    cy.get("strong").contains("everyone").should("exist");
  });

  it("redirects members away from the admin compose area", () => {
    cy.loginAsMember();
    cy.visit("/en/communications");
    cy.url().should("include", "/dashboard");
  });

  it("renders a sent announcement read-only (no Save draft / Send)", () => {
    cy.loginAsAdmin();
    cy.visit("/en/communications");
    cy.contains("td", SUBJECT).click();
    cy.url().should("match", /\/communications\/\d+$/);
    cy.contains("button", "Save draft").should("not.exist");
    cy.contains("Sent").should("be.visible");
  });
});
