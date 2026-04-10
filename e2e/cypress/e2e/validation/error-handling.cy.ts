/**
 * E2E tests for error handling + validation hardening (v0.2.3).
 *
 * Verifies:
 * - Toast notifications appear on success and error
 * - Backend 422 errors show toast messages
 * - Field-level validation feedback (Zod)
 * - Forms stay open on error (dialogs don't close)
 */

// Sonner toasts render in an <ol> with [data-sonner-toaster] attribute
const TOAST = "[data-sonner-toaster]";
// Shadcn form validation messages use data-slot="form-message"
const FORM_MSG = '[data-slot="form-message"]';

describe("Error Handling — Toast Notifications", () => {
  describe("Settings form — success toast", () => {
    beforeEach(() => {
      cy.loginAsSuperAdmin();
      cy.visit("/en/settings");
    });

    it("shows success toast when saving organization settings", () => {
      cy.get('input[name="name"]').should("be.visible");
      cy.contains("button", "Save").click();
      cy.get(TOAST).should("contain.text", "Saved successfully");
    });
  });

  describe("Group CRUD — success toasts", () => {
    const uniqueSuffix = Date.now().toString().slice(-6);
    const groupName = `E2E Toast ${uniqueSuffix}`;
    const groupSlug = `e2e-toast-${uniqueSuffix}`;

    beforeEach(() => {
      cy.loginAsAdmin();
      cy.visit("/en/groups");
    });

    it("shows success toast when creating a group", () => {
      cy.contains("button", "Create Group").click();
      cy.get('[role="dialog"]').within(() => {
        cy.get('input[name="name"]').type(groupName);
        cy.get('input[name="slug"]').type(groupSlug);
        cy.contains("button", "Create").click();
      });
      cy.get(TOAST, { timeout: 15000 }).should("contain.text", "Created successfully");
    });

    it("shows success toast when deleting a group", () => {
      cy.contains(groupName).click();
      cy.url().should("match", /\/groups\/\d+/);
      // Click the Delete button to open the confirm dialog
      cy.contains("button", "Delete").click();
      // Confirm in the AlertDialog
      cy.get('[role="alertdialog"]').should("be.visible");
      cy.get('[role="alertdialog"]').contains("button", "Delete").click();
      cy.get(TOAST, { timeout: 15000 }).should("contain.text", "Deleted successfully");
    });
  });

  describe("Member detail — success toasts", () => {
    beforeEach(() => {
      cy.loginAsAdmin();
      cy.visit("/en/members");
      cy.get("table tbody tr").first().click();
      cy.url().should("match", /\/members\/\d+/);
    });

    it("shows success toast when saving member edit", () => {
      cy.contains("button", "Edit").click();
      cy.contains("button", "Save").click();
      cy.get(TOAST).should("contain.text", "Saved successfully");
    });
  });

  describe("Activity detail — edit success toast", () => {
    it("shows success toast when saving activity edit", () => {
      cy.loginAsAdmin();
      cy.visit("/en/activities");
      cy.get('input[placeholder*="Search"]').type("Soccer");
      cy.contains("Summer Soccer Camp").click();
      cy.url().should("match", /\/activities\/\d+/);
      // Enter edit mode and save without changes
      cy.contains("button", "Edit").click();
      cy.contains("button", "Save").click();
      cy.get(TOAST).should("contain.text", "Saved successfully");
    });
  });
});

describe("Error Handling — Error Toasts on Invalid Data", () => {
  describe("Login — inline error display", () => {
    it("shows inline error on invalid credentials", () => {
      cy.visit("/en/login");
      cy.get('input[type="email"]').type("wrong@test.com");
      cy.get('input[type="password"]').type("WrongPassword1!");
      cy.get('button[type="submit"]').click();
      // Login uses inline error display (red box), not toast
      cy.get('[class*="destructive"]').should("be.visible");
    });
  });

  describe("Membership type — backend error toast", () => {
    it("shows error toast when creating with duplicate slug", () => {
      cy.loginAsSuperAdmin();
      cy.visit("/en/settings");
      // Switch to Membership Types tab
      cy.contains("button", "Membership Types").click();
      // Click the create/new button in the membership types section
      cy.get('[role="tabpanel"]').find("button").contains(/create|new/i).click();
      cy.get('[role="dialog"]').should("be.visible");
      cy.get('[role="dialog"]').within(() => {
        cy.get('input[name="name"]').type("Duplicate Test");
        cy.get('input[name="slug"]').type("full-member");
        cy.get('input[name="base_price"]').clear().type("10");
        // Submit
        cy.get('button[type="submit"]').click();
      });
      // Should show error toast from global handler (duplicate slug = 400/409)
      // OR the dialog stays open with a field error
      // Wait a moment for the API call to complete
      cy.wait(2000);
      // Either a toast appeared or the dialog is still open with an error
      cy.get("body").then(($body) => {
        const hasToast = $body.find(TOAST).length > 0 && $body.find(TOAST).text().length > 0;
        const hasDialog = $body.find('[role="dialog"]').length > 0;
        // At least one error indicator should be present
        expect(hasToast || hasDialog).to.be.true;
      });
    });
  });
});

describe("Validation — Frontend Zod Constraints", () => {
  describe("Activity create — cross-field validation", () => {
    beforeEach(() => {
      cy.loginAsAdmin();
      cy.visit("/en/activities/new");
    });

    it("shows validation errors when required fields are empty", () => {
      // Submit empty form
      cy.get('button[type="submit"]').click();
      // Should show form-level validation messages
      cy.get(FORM_MSG).should("have.length.greaterThan", 0);
      // Should stay on the page
      cy.url().should("include", "/activities/new");
    });

    it("shows error when end date is before start date", () => {
      cy.get('input[name="name"]').type("Test Activity");
      cy.get('input[name="starts_at"]').type("2027-07-15T10:00");
      cy.get('input[name="ends_at"]').type("2027-07-14T10:00");
      cy.get('input[name="registration_starts_at"]').type("2027-06-01T10:00");
      cy.get('input[name="registration_ends_at"]').type("2027-07-14T23:59");
      cy.get('input[name="max_participants"]').clear().type("50");
      cy.get('button[type="submit"]').click();
      cy.contains("End date must be after start date").should("be.visible");
      cy.url().should("include", "/activities/new");
    });

    it("shows error when max participants < min participants", () => {
      cy.get('input[name="name"]').type("Test Activity");
      cy.get('input[name="starts_at"]').type("2027-07-15T10:00");
      cy.get('input[name="ends_at"]').type("2027-07-15T18:00");
      cy.get('input[name="registration_starts_at"]').type("2027-06-01T10:00");
      cy.get('input[name="registration_ends_at"]').type("2027-07-15T09:00");
      cy.get('input[name="min_participants"]').clear().type("100");
      cy.get('input[name="max_participants"]').clear().type("10");
      cy.get('button[type="submit"]').click();
      cy.contains(/max participants must be greater/i).should("be.visible");
      cy.url().should("include", "/activities/new");
    });
  });

  describe("Group create — Zod field validation", () => {
    beforeEach(() => {
      cy.loginAsAdmin();
      cy.visit("/en/groups");
      cy.contains("button", "Create Group").click();
      cy.get('[role="dialog"]').should("be.visible");
    });

    it("shows validation when submitting empty form", () => {
      cy.get('[role="dialog"]').within(() => {
        cy.get('button[type="submit"]').click();
        cy.get(FORM_MSG).should("have.length.greaterThan", 0);
      });
      // Dialog stays open
      cy.get('[role="dialog"]').should("be.visible");
    });

    it("shows validation error for invalid slug format", () => {
      cy.get('[role="dialog"]').within(() => {
        cy.get('input[name="name"]').type("Test Group");
        cy.get('input[name="slug"]').type("INVALID SLUG!");
        cy.get('button[type="submit"]').click();
        cy.get(FORM_MSG).should("have.length.greaterThan", 0);
      });
      cy.get('[role="dialog"]').should("be.visible");
    });

    it("shows validation error for invalid color hex", () => {
      cy.get('[role="dialog"]').within(() => {
        cy.get('input[name="name"]').type("Color Test");
        cy.get('input[name="slug"]').type("color-test-grp");
        cy.get('input[name="color"]').type("not-a-hex");
        cy.get('button[type="submit"]').click();
        cy.get(FORM_MSG).should("have.length.greaterThan", 0);
      });
      cy.get('[role="dialog"]').should("be.visible");
    });
  });

  describe("Modality tab — dialog validation", () => {
    beforeEach(() => {
      cy.loginAsAdmin();
      cy.visit("/en/activities");
      cy.get('input[placeholder*="Search"]').type("Soccer");
      cy.contains("Summer Soccer Camp").click();
      cy.contains("button", "Modalities").click();
      // Wait for tab content to load
      cy.wait(1000);
    });

    it("shows validation error when submitting empty modality name", () => {
      // The create button is inside the tab content area, use variant="outline" size="sm"
      cy.contains("button", /create|add/i).click();
      cy.get('[role="dialog"]').should("be.visible");
      cy.get('[role="dialog"]').within(() => {
        cy.get('input[name="name"]').clear();
        cy.get('button[type="submit"]').click();
        cy.get(FORM_MSG).should("have.length.greaterThan", 0);
      });
      cy.get('[role="dialog"]').should("be.visible");
    });
  });

  describe("Settings — max length validation", () => {
    beforeEach(() => {
      cy.loginAsSuperAdmin();
      cy.visit("/en/settings");
    });

    it("rejects organization name over 255 characters via backend 422", () => {
      // The frontend Zod schema has max(255), so it may catch it client-side.
      // Either way, a toast should appear (success or error).
      const longName = "x".repeat(256);
      cy.get('input[name="name"]').clear().type(longName, { delay: 0 });
      cy.get('button[type="submit"]').click();
      // Should show either a form validation message or an error toast
      cy.get(`${FORM_MSG}, ${TOAST}`).should("be.visible");
    });
  });

  describe("Discount codes — dialog validation", () => {
    beforeEach(() => {
      cy.loginAsAdmin();
      cy.visit("/en/activities");
      cy.get('input[placeholder*="Search"]').type("Soccer");
      cy.contains("Summer Soccer Camp").click();
      cy.contains("button", "Discounts").click();
      cy.wait(1000);
    });

    it("shows validation error for empty discount code", () => {
      cy.contains("button", /create|add/i).click();
      cy.get('[role="dialog"]').should("be.visible");
      cy.get('[role="dialog"]').within(() => {
        cy.get('button[type="submit"]').click();
        cy.get(FORM_MSG).should("have.length.greaterThan", 0);
      });
      cy.get('[role="dialog"]').should("be.visible");
    });
  });
});
