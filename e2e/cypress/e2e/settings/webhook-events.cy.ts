// The admin view of payment notifications memship could not apply or ignored (#435).
describe("Payment notifications — Super Admin", () => {
  const API_URL = Cypress.env("API_URL") || "http://localhost:8003/api/v1";
  // The same values stripe-checkout.cy.ts activates, so the two specs agree
  // on the provider whichever runs first.
  const config = {
    secret_key: "sk_test_e2e",
    publishable_key: "pk_test_e2e",
    webhook_secret: "whsec_test_e2e",
    mode: "webhook",
  };
  const eventId = `evt_e2e_ignored_${Date.now()}`;

  async function stripeSignature(payload: string, secret: string): Promise<string> {
    const timestamp = Math.floor(Date.now() / 1000);
    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );
    const mac = await crypto.subtle.sign(
      "HMAC",
      key,
      new TextEncoder().encode(`${timestamp}.${payload}`)
    );
    const hex = Array.from(new Uint8Array(mac))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    return `t=${timestamp},v1=${hex}`;
  }

  before(() => {
    cy.apiLogin("super@examplee6e3b1.com", "TestSuper1!");
    cy.request(`${API_URL}/payment-providers/`).then((list) => {
      const stripe = list.body.items.find(
        (p: { provider_type: string }) => p.provider_type === "stripe"
      );
      if (stripe) {
        cy.request("PUT", `${API_URL}/payment-providers/${stripe.id}`, {
          status: "test",
          config,
        });
      } else {
        cy.request("POST", `${API_URL}/payment-providers/`, {
          provider_type: "stripe",
          display_name: "Stripe Test",
          status: "test",
          config,
          is_default: false,
        });
      }
    });

    // A correctly signed notification of a type memship does not handle is
    // recorded as `ignored` — the status a double charge also lands in.
    // Shaped like a real Stripe event: the SDK needs `object: "event"` to
    // build the event it verifies.
    const payload = JSON.stringify({
      id: eventId,
      object: "event",
      type: "customer.created",
      data: { object: { id: "cus_e2e", object: "customer" } },
    });
    cy.wrap(null)
      .then(() => stripeSignature(payload, config.webhook_secret))
      .then((signature) => {
        cy.request({
          method: "POST",
          url: `${API_URL}/webhooks/stripe`,
          body: payload,
          headers: { "Content-Type": "application/json", "Stripe-Signature": signature },
        })
          .its("status")
          .should("eq", 200);
      });
  });

  beforeEach(() => {
    cy.loginAsSuperAdmin();
    cy.visit("/en/settings");
    cy.settingsTab("Payments", "Payment Providers");
  });

  it("lists an ignored notification with its reason", () => {
    cy.get("[data-testid='webhook-events']").within(() => {
      cy.contains("Payment notifications").should("be.visible");
      cy.contains("tr", "customer.created")
        .should("contain", "Ignored")
        .and("contain", "Unhandled event type: customer.created");
    });
  });

  it("keeps ignored ones listed when processed ones are shown too", () => {
    cy.get("[data-testid='webhook-events']").within(() => {
      cy.contains("label", "Also show processed ones").should("be.visible");
      cy.get("button[role='switch']").click();
      cy.contains("tr", "customer.created").should("be.visible");
    });
  });
});
