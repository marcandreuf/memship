import { TEST_ACCOUNTS } from "./commands";

// Builders for the pay-to-confirm specs (#591). Each spec creates the
// activities it needs and cancels them afterwards, so no spec sees another's
// seats and the seeded catalogue is never written to.

export const API = Cypress.env("API_URL") || "http://localhost:8003/api/v1";

type Account = { email: string; password: string };

export interface PaidActivityOptions {
  maxParticipants?: number;
  waitingList?: boolean;
  paymentMethods?: string[];
  autoCancel?: boolean;
  amount?: number;
  publish?: boolean;
  allowSelfCancellation?: boolean;
  /** The refund deadline in minutes before the start (#604), and what follows it. */
  cancellationPolicy?: { deadlineMinutes: number; lateMode: "block" | "allow_no_refund" };
}

function isoIn(days: number) {
  return new Date(Date.now() + days * 86400000).toISOString();
}

/** Create (and by default publish) a pay-to-confirm activity as the admin. */
export function createPaidActivity(name: string, options: PaidActivityOptions = {}) {
  const {
    maxParticipants = 10,
    waitingList = false,
    paymentMethods = ["cash"],
    autoCancel,
    amount = 20,
    publish = true,
    allowSelfCancellation = false,
    cancellationPolicy,
  } = options;
  cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
  return cy
    .request("POST", `${API}/activities`, {
      name,
      starts_at: isoIn(30),
      ends_at: isoIn(31),
      registration_starts_at: isoIn(-1),
      registration_ends_at: isoIn(29),
      max_participants: maxParticipants,
      features: { waiting_list: waitingList },
      payment_methods: paymentMethods,
      allow_self_cancellation: allowSelfCancellation,
      ...(cancellationPolicy
        ? {
            self_cancellation_deadline_minutes: cancellationPolicy.deadlineMinutes,
            late_cancellation_mode: cancellationPolicy.lateMode,
          }
        : {}),
      ...(autoCancel === undefined ? {} : { auto_cancel_enabled: autoCancel, auto_cancel_hours: 48 }),
    })
    .then((r) => {
      const id = r.body.id as number;
      cy.request("POST", `${API}/activities/${id}/prices`, { name: "Entry", amount, is_default: true });
      if (publish) cy.request("PUT", `${API}/activities/${id}/publish`);
      return cy.wrap(id);
    });
}

/** Cancel an activity built by a spec; tolerant of one already gone. */
export function cancelActivity(id: number | undefined) {
  if (id === undefined) return;
  cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
  cy.request({ method: "PUT", url: `${API}/activities/${id}/cancel`, failOnStatusCode: false });
}

/** Register `account` in the activity at its default price; yields the registration. */
export function registerAs(account: Account, activityId: number) {
  cy.apiLogin(account.email, account.password);
  return cy.request(`${API}/activities/${activityId}`).then((activity) =>
    cy
      .request("POST", `${API}/activities/${activityId}/register`, { price_id: activity.body.prices[0].id })
      .then((r) => cy.wrap(r.body as { id: number; status: string; receipt_id: number | null }))
  );
}

/** Pay a seat's receipt in cash as the admin, which confirms the seat. */
export function payInCash(receiptId: number) {
  cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
  cy.request("POST", `${API}/receipts/${receiptId}/pay`, { payment_method: "cash" });
}
