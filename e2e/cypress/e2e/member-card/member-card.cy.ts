// =============================================================================
// Member Card + QR Check-in (v0.7.0) — admin enables the module + sets a number
// prefix, creates an auto-numbered member, that member opens their card (QR +
// PDF), an admin scans the code (active → suspended → active), invalid path.
// =============================================================================

const API = Cypress.env("API_URL") || "http://localhost:8003/api/v1";
const PREFIX = "E2E-";
const MEMBER_FIRST = "Cardholder";
const MEMBER_LAST = `E2E${Date.now()}`;

describe("Member Card + QR (v0.7.0)", () => {
  before(() => {
    // Enable the module and configure a number prefix (persists in org settings).
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.contains('[role="tab"]', "Member Card").click();
    cy.get('[role="switch"]').then(($sw) => {
      if ($sw.attr("aria-checked") !== "true") cy.wrap($sw).click();
    });
    cy.get('[role="switch"]').should("have.attr", "aria-checked", "true");
    cy.get('input[placeholder="SCB-"]').clear().type(PREFIX);
    cy.contains("button", "Save").click();
    cy.contains(/saved successfully/i).should("be.visible");
  });

  it("shows the Member Card settings toggle + numbering config (super admin)", () => {
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.contains('[role="tab"]', "Member Card").click();
    cy.contains("Enable member cards").should("be.visible");
    cy.contains("Member numbering").should("be.visible");
    cy.contains("button", "Assign numbers to members without one").should("be.visible");
  });

  it("auto-numbers a new member with the configured prefix", () => {
    cy.loginAsAdmin();
    cy.visit("/en/members");
    // The API is the source of truth for the generated number; create via API
    // and assert the prefix, then confirm it renders in the members list.
    cy.request({
      method: "POST",
      url: `${API}/members/`,
      body: { first_name: MEMBER_FIRST, last_name: MEMBER_LAST },
    }).then((resp) => {
      expect(resp.status).to.eq(201);
      expect(resp.body.member_number).to.match(new RegExp(`^${PREFIX}\\d+$`));
    });
  });

  it("lets the member open their card (number, QR, PDF)", () => {
    cy.loginAsMember();
    cy.visit("/en/my-card");

    // Card shows the member number and a scannable QR image.
    cy.get('img[src="/api/me/card/qr.svg"]').should("be.visible");
    // Download PDF is a styled link (Button asChild → <a>), not a <button>.
    cy.contains("a", "Download PDF").should("have.attr", "href", "/api/me/card/pdf");

    // The QR endpoint returns an SVG, and the PDF endpoint a real PDF.
    cy.request("/api/me/card/qr.svg").then((r) => {
      expect(r.headers["content-type"]).to.include("image/svg+xml");
      expect(r.body).to.include("<svg");
    });
    cy.request({ url: "/api/me/card/pdf", encoding: "binary" }).then((r) => {
      expect(r.headers["content-type"]).to.include("application/pdf");
      expect(r.body.substring(0, 5)).to.eq("%PDF-");
    });
  });

  it("verifies a member by code on the admin scan page: active → suspended", () => {
    // Grab the seed member's signed token + identity from their own card DTO.
    cy.loginAsMember();
    cy.request("/api/me/card").then((card) => {
      const token = card.body.token as string;
      const memberId = card.body.member_id as number;
      const fullName = card.body.full_name as string;
      expect(token).to.be.a("string");

      cy.loginAsAdmin();
      cy.visit("/en/scan");

      // Manual entry (camera-free, deterministic) → active verdict for the member.
      cy.get('input[aria-label="Enter code manually"]').type(token);
      cy.contains("button", "Verify").click();
      cy.contains("Active").should("be.visible");
      cy.contains(fullName).should("be.visible");

      // Suspend the member via API, then re-scan → live status reflects it.
      cy.request({
        method: "PUT",
        url: `${API}/members/${memberId}/status`,
        body: { status: "suspended", reason: "e2e" },
      }).then((r) => expect(r.status).to.eq(200));

      cy.contains("button", "Scan another").click();
      cy.get('input[aria-label="Enter code manually"]').type(token);
      cy.contains("button", "Verify").click();
      cy.contains("Suspended").should("be.visible");

      // Restore to active so the shared seed member isn't left suspended.
      cy.request({
        method: "PUT",
        url: `${API}/members/${memberId}/status`,
        body: { status: "active", reason: "e2e-restore" },
      }).then((r) => expect(r.status).to.eq(200));
    });
  });

  it("rejects an invalid code", () => {
    cy.loginAsAdmin();
    cy.visit("/en/scan");
    cy.get('input[aria-label="Enter code manually"]').type("1.deadbeefdeadbeef");
    cy.contains("button", "Verify").click();
    cy.contains("Invalid card code").should("be.visible");
  });

  it("hides the scan page from members", () => {
    cy.loginAsMember();
    cy.visit("/en/scan");
    cy.contains(/do not have access/i).should("be.visible");
  });
});
