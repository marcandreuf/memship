import { TEST_ACCOUNTS } from "../../support/commands";
import { API } from "../../support/pay-to-confirm";

// #598: a link to an activity, shared into a chat or a social post, should
// survive the sign-in. Until now the login screen read only `error` and
// `expired`, so every sign-in landed on the dashboard whatever the visitor had
// asked for, and a promoted activity link dropped them somewhere else.
//
// The open-redirect cases below are the reason this is not a two-line change:
// `next` is attacker-supplied in a crafted link, and `isInternalPath` in
// `lib/return-to.ts` is what refuses it.

function signIn(account: { email: string; password: string }) {
  cy.get('input[type="email"]').clear().type(account.email);
  cy.get('input[type="password"]').clear().type(account.password);
  cy.get('button[type="submit"]').click();
}

describe("Returning to the page a link asked for (#598)", () => {
  let registerPath: string;

  before(() => {
    // By name, not by id: ids are seed-dependent.
    cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
    cy.request(`${API}/activities?search=Chess Club Tournament`).then((r) => {
      const activity = r.body.items.find(
        (a: { name: string }) => a.name === "Chess Club Tournament",
      );
      expect(activity, "seeded Chess Club Tournament").to.exist;
      registerPath = `/activities/${activity.id}/register`;
    });
  });

  beforeEach(() => {
    cy.clearCookies();
  });

  it("sends a shared activity link through login and on to the form", () => {
    cy.visit(`/en${registerPath}`);
    cy.url().should("include", "/login");
    cy.url().should("include", "next=");

    signIn(TEST_ACCOUNTS.member);

    cy.url().should("include", registerPath);
    cy.url().should("not.include", "/dashboard");
  });

  it("still lands on the dashboard when no destination was asked for", () => {
    cy.visit("/en/login");
    signIn(TEST_ACCOUNTS.member);
    cy.url().should("include", "/dashboard");
  });

  // The three shapes `isInternalPath` distinguishes. Each must fall back to the
  // dashboard silently — someone handed a crafted link is not shown an error
  // about it.
  const CRAFTED = [
    { label: "protocol-relative", value: "//evil.com" },
    { label: "absolute", value: "https://evil.com" },
    { label: "backslash", value: "/\\evil.com" },
  ];

  CRAFTED.forEach(({ label, value }) => {
    it(`refuses a ${label} destination and lands on the dashboard`, () => {
      cy.visit(`/en/login?next=${encodeURIComponent(value)}`);
      signIn(TEST_ACCOUNTS.member);

      cy.url().should("include", "/dashboard");
      cy.location("origin").should("eq", Cypress.config("baseUrl"));
      cy.location("hostname").should("not.contain", "evil");
    });
  });

  it("refuses to return to the login page itself", () => {
    cy.visit("/en/login?next=%2Flogin");
    signIn(TEST_ACCOUNTS.member);
    cy.url().should("include", "/dashboard");
  });

  it("returns an expired session to the page it was on", () => {
    cy.loginAsMember();
    cy.visit("/en/my-activities");
    cy.contains(/my activities/i).should("be.visible");

    // The session goes away underneath them, the way a real expiry does.
    cy.clearCookie("access_token");
    cy.contains("a", "My Receipts").click();

    cy.url().should("include", "/login");
    cy.url().should("include", "expired=1");
    cy.url().should("include", "next=");
  });
});
