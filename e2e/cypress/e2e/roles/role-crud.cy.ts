/// <reference types="cypress" />

// Authoring roles is reserved to the super admin: `roles.write` is a reserved
// permission key, so no custom role can ever reach this screen.
describe("Roles — authoring", { tags: ["@roles"] }, () => {
  const roleName = `Coordinator ${Date.now()}`;

  beforeEach(() => {
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.contains("button", "Roles").click();
  });

  it("creates a role from the permission catalog", { tags: ["@smoke"] }, () => {
    cy.contains("button", "Create role").click();

    cy.get('[data-testid="role-name"]').type(roleName);
    cy.get('[data-testid="permission-activities.read"]').click();
    cy.get('[data-testid="permission-activities.write"]').click();
    cy.contains("button", "Save").click();

    cy.contains(roleName).should("be.visible");
  });

  it("renders each permission with its description", () => {
    cy.contains("button", "Create role").click();
    // The catalog outgrew the dialog: `billing.runs.write` now sits below the
    // fold in a scrollable, position-fixed panel, so it is present but not in
    // view. Scroll to it rather than assert on where it happens to land.
    cy.contains("Run bulk billing").scrollIntoView().should("be.visible");
    cy.contains("Generate fees across the whole club at once").should("be.visible");
  });

  it("refuses a reserved permission on a custom role", () => {
    cy.contains("button", "Create role").click();
    // roles.write / settings.integrations.write are superadmin-only by design.
    cy.get('[data-testid="permission-roles.write"]').should("be.disabled");
    cy.get('[data-testid="permission-settings.integrations.write"]').should(
      "be.disabled"
    );
  });

  it("edits the role it just created", () => {
    cy.contains("tr", roleName).contains("button", "Edit").click();
    cy.get('[data-testid="permission-reports.read"]').click();
    cy.contains("button", "Save").click();
    cy.contains(roleName).should("be.visible");
  });

  it("refuses to delete a role that is still assigned", () => {
    // `treasurer` is seeded and held by treasurer@test.com.
    cy.get('[data-testid="role-row-treasurer"]')
      .contains("button", "Delete")
      .click();
    cy.get('[role="alertdialog"]').contains("button", "Delete").click();
    cy.contains(/Cannot delete: \d+ accounts still hold it/).should("be.visible");
    cy.get('[data-testid="role-row-treasurer"]').should("exist");
  });

  it("locks the system roles", () => {
    // Name and deletion are fixed; only the permission set is tunable, so
    // `admin` offers Edit but no Delete, and `super_admin` offers neither.
    cy.get('[data-testid="role-row-admin"]').within(() => {
      cy.contains("System").should("be.visible");
      cy.contains("button", "Edit").should("exist");
      cy.contains("button", "Delete").should("not.exist");
    });
    cy.get('[data-testid="role-row-super_admin"]').within(() => {
      cy.contains("button", "Edit").should("not.exist");
      cy.contains("button", "Delete").should("not.exist");
    });
  });

  it("keeps a system role's name read-only while its permissions stay editable", () => {
    cy.get('[data-testid="role-row-admin"]').contains("button", "Edit").click();
    cy.get('[data-testid="role-name"]').should("be.disabled");
    cy.get('[data-testid="permission-members.read"]').should("not.be.disabled");
  });

  it("deletes an unassigned role", () => {
    cy.contains("tr", roleName).contains("button", "Delete").click();
    cy.get('[role="alertdialog"]').contains("button", "Delete").click();
    cy.contains(roleName).should("not.exist");
  });
});
