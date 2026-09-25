// An emptied field used to be sent as `undefined`, which JSON.stringify drops,
// so the partial update kept the old value while the UI said "Saved" (#283).
const API = Cypress.env("API_URL") || "http://localhost:8003/api/v1";

describe("Member edit — clearing a field", () => {
  let memberId: number;

  beforeEach(() => {
    cy.loginAsAdmin();
    cy.request({
      method: "POST",
      url: `${API}/members/`,
      body: {
        first_name: "Clear",
        last_name: `Field ${Date.now()}`,
        national_id: "12345678Z",
      },
    }).then((r) => {
      expect(r.status).to.eq(201);
      memberId = r.body.id;
    });
  });

  it("clears the national ID when the field is emptied", () => {
    cy.visit(`/en/members/${memberId}`);
    cy.contains("12345678Z").should("be.visible");

    cy.contains("button", "Edit").click();
    cy.contains("label", "National ID").parent().find("input").clear();
    cy.contains("button", "Save").click();
    cy.contains(/saved successfully/i).should("be.visible");

    cy.contains("12345678Z").should("not.exist");
    cy.request(`${API}/members/${memberId}`)
      .its("body.person.national_id")
      .should("be.null");
  });
});

describe("Membership type edit — removing the group", () => {
  const stamp = Date.now();
  const typeName = `No Group Type ${stamp}`;
  let groupId: number;
  let typeId: number;

  beforeEach(() => {
    cy.loginAsAdmin();
    cy.request("POST", `${API}/groups/`, {
      name: `Clear Group ${stamp}`,
      slug: `clear-group-${stamp}`,
    }).then((g) => {
      groupId = g.body.id;
      // Inactive, so members' plan lists and the specs reading them never see it.
      cy.request("POST", `${API}/membership-types/`, {
        name: typeName,
        slug: `no-group-type-${stamp}`,
        group_id: groupId,
        is_active: false,
      }).then((mt) => {
        typeId = mt.body.id;
      });
    });
  });

  afterEach(() => {
    cy.request({ method: "DELETE", url: `${API}/membership-types/${typeId}`, failOnStatusCode: false });
    cy.request({ method: "DELETE", url: `${API}/groups/${groupId}`, failOnStatusCode: false });
  });

  it("offers No group and saves it", () => {
    cy.visit("/en/settings");
    cy.settingsTab("Members", "Membership Types");
    cy.contains("tr", typeName).contains("button", "Edit").click();

    cy.get('[role="dialog"]').within(() => {
      cy.contains("label", "Group").parent().find('[role="combobox"]').click();
    });
    cy.contains('[role="option"]', "No group").click();
    cy.get('[role="dialog"]').contains("button", "Save").click();
    cy.contains(/saved successfully/i).should("be.visible");

    cy.request(`${API}/membership-types/${typeId}`).its("body.group_id").should("be.null");
  });
});
