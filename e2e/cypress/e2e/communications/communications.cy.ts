// =============================================================================
// Communications (v0.5.0 + v0.5.1) — admin compose/send, member notifications,
// RBAC, and the sent view (content header + details/recipients tabs).
// =============================================================================

const SUBJECT = "E2E Broadcast Announcement";
const SUBJECT_DIRECT = "E2E Direct Send Announcement";

describe("Communications (v0.5.0 + v0.5.1)", () => {
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

    // Lands on the sent view (content header + tabs), not the compose form.
    cy.url().should("match", /\/communications\/\d+$/);
    cy.contains(/recipients/i).should("be.visible");
    cy.contains("button", "Save draft").should("not.exist");
  });

  it("composes and sends in one action from the new form (v0.5.1)", () => {
    cy.loginAsAdmin();
    cy.visit("/en/communications/new");

    cy.get('input[maxlength="200"]').type(SUBJECT_DIRECT);
    cy.get("textarea").type("Direct one-shot send — no intermediate draft step.");
    // Send is available immediately on the new form (no prior Save draft).
    cy.contains("button", "Send").click();
    cy.get('[role="dialog"]').within(() => {
      cy.contains(/send announcement\?/i).should("be.visible");
      cy.contains("button", "Send").click();
    });

    // Created + sent in one go → sent view.
    cy.url().should("match", /\/communications\/\d+$/);
    cy.contains(/recipients/i).should("be.visible");

    // And it shows up as sent in the history.
    cy.visit("/en/communications");
    cy.contains("td", SUBJECT_DIRECT).should("be.visible");
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

  it("shows the sent view: content header, details, and a lazy recipients tab (v0.5.1)", () => {
    cy.loginAsAdmin();
    cy.visit("/en/communications");
    cy.contains("td", SUBJECT).click();
    cy.url().should("match", /\/communications\/\d+$/);

    // Sent view, not the compose form.
    cy.contains("button", "Save draft").should("not.exist");
    // Content header summary line.
    cy.contains(/recipients/i).should("be.visible");
    // Details tab is the default; shows delivery metadata.
    cy.contains(/Sent by/i).should("be.visible");

    // Recipients tab loads on demand and lists the audience in a paginated table
    // with a Seen column (read state per recipient).
    cy.contains('[role="tab"]', "Recipients").click();
    cy.get("table tbody tr").should("have.length.greaterThan", 0);
    cy.contains("th", "Seen").should("be.visible");
  });
});
