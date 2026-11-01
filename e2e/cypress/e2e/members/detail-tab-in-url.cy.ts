/**
 * The open tab belongs in the URL, not in component state (memship#471).
 *
 * Opening a record from a tab used to be a one-way trip: nothing recorded
 * which tab had been left, so coming back landed on the record's first tab.
 *
 * Every assertion on the tab itself targets `[role="tab"]` rather than a text
 * query. `TabsNav` renders a select beside the bar that repeats the active
 * tab's label, so matching on text alone can resolve to whichever of the two
 * is hidden at the current viewport.
 *
 * The URL is asserted explicitly rather than waited on: the nuqs setters have
 * a known race with row-click navigation (memship#468), and an implicit wait
 * would hide it.
 */
describe("Member detail — the open tab is in the URL", () => {
  let detail: string;

  beforeEach(() => {
    cy.loginAsAdmin();
    cy.visit("/en/members");
    cy.get("table tbody tr").first().click();
    cy.url().should("match", /\/members\/\d+/);
    cy.url().then((url) => {
      detail = new URL(url).pathname;
    });
  });

  const activeTab = () => cy.get('[role="tab"][data-state="active"]');

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


  it("names the tab in the URL when one is opened", () => {
    tab("Activities").click();

    cy.url().should("include", "tab=activities");
    activeTab().should("contain.text", "Activities");
  });

  it("opens the tab the URL names, on a cold load", () => {
    cy.then(() => cy.visit(`${detail}?tab=activities`));

    activeTab().should("contain.text", "Activities");
    cy.url().should("include", "tab=activities");
  });

  it("falls back to the first tab when the URL names one that does not exist", () => {
    // A stale link, or a tab the caller omitted for this user. It must not
    // render an empty panel.
    cy.then(() => cy.visit(`${detail}?tab=no-such-tab`));

    activeTab().should("exist").and("not.contain.text", "no-such-tab");
    cy.get('[role="tabpanel"]').should("exist");
  });

  it("returns to the tab that was left, not to the first one", () => {
    tab("Activities").click();
    cy.url().should("include", "tab=activities");

    cy.get("nav[aria-label='breadcrumb']").contains("Members").click();
    cy.url().should("match", /\/members(\?|$)/);

    cy.go("back");

    cy.url().should("include", "tab=activities");
    activeTab().should("contain.text", "Activities");
  });

  it("switching tabs does not stack history entries", () => {
    // The setter replaces rather than pushes, so Back leaves the record
    // instead of walking backwards through every tab that was looked at.
    tab("Activities").click();
    cy.url().should("include", "tab=activities");
    tab("Receipts").click();
    cy.url().should("include", "tab=receipts");

    cy.go("back");

    cy.url().should("match", /\/members(\?|$)/);
  });
});
