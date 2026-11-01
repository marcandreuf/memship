/**
 * A record opened from another record leads back to it (memship#471).
 *
 * Every detail page hardcoded its first breadcrumb to its own module list, but
 * a record has several parents: a member is reachable from the members list,
 * from a group's members tab and from the paid-tier report. The static crumb
 * therefore named a parent the user had not come through, and there was no way
 * back at all.
 *
 * The navigating side now appends where it is and what to call it, and
 * `DetailHeader` swaps that in for the static crumb.
 *
 * The rejection cases matter as much as the happy path: the value arrives from
 * the query string, so it is attacker-supplied in a crafted link, and
 * rendering it unchecked would make the breadcrumb an open redirect. The
 * frontend has no unit test runner, so these assert the rendered page instead.
 */
describe("Detail breadcrumb — where the record was opened from", () => {
  let detail: string;

  const breadcrumb = () => cy.get("nav[aria-label='breadcrumb']");

/**
 * A tab by its exact label, tolerating a badge.
 *
 * Two traps, both met for real while writing this. A tab's text includes its
 * badge count when it has one, so `Receipts` renders as `Receipts3` on a member
 * who has receipts and as `Receipts` on one who does not — a substring match
 * hides that, an exact match fails on whichever member the list happens to put
 * first. And a sibling label can contain another's: `Membership Types` contains
 * `Members`, so a substring match clicks the wrong tab, and when that one is
 * already active Radix fires no change and nothing reaches the URL.
 */
const tab = (label: string) =>
  cy.contains('[role="tab"]', new RegExp(`^${label}(\\s*\\d+)?$`));


  describe("arriving from a group's members tab", () => {
    it("names the group and leads back to the tab that was left", () => {
      cy.loginAsAdmin();
      cy.visit("/en/groups");
      cy.get("table tbody tr").first().click();
      cy.url().should("match", /\/groups\/\d+/);

      cy.url().then((groupUrl) => {
        const group = new URL(groupUrl).pathname;

        cy.get("h1")
          .invoke("text")
          .then((groupName) => {
            tab("Members").click();
            cy.url().should("include", "tab=members");

            cy.get("table tbody tr").first().click();
            cy.url().should("match", /\/members\/\d+/);

            // The trail names the group, not "Members".
            breadcrumb().should("contain.text", groupName.trim());

            // And it is a link back to the group with the tab still open.
            breadcrumb()
              .contains("a", groupName.trim())
              .should("have.attr", "href")
              .and("include", group)
              .and("include", "tab=members");
          });
      });
    });
  });


  describe("arriving from a paged list", () => {
    it("comes back to the page that was left, not to page one", () => {
      // The milder instance of the same gap: list state is already URL-backed,
      // but a row click pushed a bare detail path and the static crumb linked
      // to the bare list, so a filtered, paged list returned as page one.
      // 56 members at 20 per page, so page 2 always has rows.
      cy.loginAsAdmin();
      cy.visit("/en/members?page=2");
      cy.url().should("include", "page=2");

      cy.get("table tbody tr").first().click();
      cy.url().should("match", /\/members\/\d+/);

      // Same label as the static crumb it replaced; the href is what changed.
      breadcrumb()
        .contains("a", "Members")
        .should("have.attr", "href")
        .and("include", "page=2");
    });
  });

  describe("the return target is validated before it is rendered", () => {
    beforeEach(() => {
      cy.loginAsAdmin();
      cy.visit("/en/members");
      cy.get("table tbody tr").first().click();
      cy.url().should("match", /\/members\/\d+/);
      cy.url().then((url) => {
        detail = new URL(url).pathname;
      });
    });

    it("renders an internal path as the first crumb", () => {
      cy.then(() =>
        cy.visit(`${detail}?from=%2Fgroups%2F1%3Ftab%3Dmembers&fromLabel=Adult%20Members`),
      );

      breadcrumb().contains("a", "Adult Members").should("have.attr", "href").and("include", "/groups/1");
      // The static crumb it replaced is gone, so the trail describes the path taken.
      breadcrumb().should("not.contain.text", "Members list");
    });

    it("ignores an absolute URL", () => {
      cy.then(() => cy.visit(`${detail}?from=https%3A%2F%2Fevil.example%2Fx&fromLabel=Evil`));

      breadcrumb().should("not.contain.text", "Evil");
      breadcrumb().find("a").each(($a) => {
        expect($a.attr("href") || "").not.to.contain("evil.example");
      });
    });

    it("ignores a protocol-relative URL", () => {
      // `//evil.example` is a real URL to a different host, and it starts with
      // a slash, which is what a naive "must start with /" check would accept.
      cy.then(() => cy.visit(`${detail}?from=%2F%2Fevil.example%2Fx&fromLabel=Evil`));

      breadcrumb().should("not.contain.text", "Evil");
      breadcrumb().find("a").each(($a) => {
        expect($a.attr("href") || "").not.to.contain("evil.example");
      });
    });

    it("ignores a backslash, which a browser may normalise to a slash", () => {
      cy.then(() => cy.visit(`${detail}?from=%2F%5Cevil.example%2Fx&fromLabel=Evil`));

      breadcrumb().should("not.contain.text", "Evil");
    });

    it("ignores a path with no label, which has nothing to render", () => {
      cy.then(() => cy.visit(`${detail}?from=%2Fgroups%2F1`));

      breadcrumb().find("a").each(($a) => {
        expect($a.attr("href") || "").not.to.equal("/groups/1");
      });
    });

    it("keeps the static crumb when the URL says nothing", () => {
      cy.then(() => cy.visit(detail));

      breadcrumb().contains("a", "Members").should("have.attr", "href").and("include", "/members");
    });
  });
});
