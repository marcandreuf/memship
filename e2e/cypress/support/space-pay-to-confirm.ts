import { TEST_ACCOUNTS } from "./commands";

// Builders for the pay-to-confirm space specs (#603). Each spec creates the
// spaces it needs and removes them afterwards, so no spec sees another's
// bookings. Global settings are only ever switched on.

export const API = Cypress.env("API_URL") || "http://localhost:8003/api/v1";

/** A second seeded member, for the cases one booking holder cannot show. */
export const SECOND_MEMBER = { email: "nuria@examplee6e3b1.com", password: "TestMember1!" };

const BOOKING_MAILS = ["booking_pending_payment", "booking_deadline_reminder", "booking_cancelled_unpaid"];

type Account = { email: string; password: string };
export type Booking = { id: number; status: string; space_id?: number; receipt_id?: number | null };

/** "YYYY-MM-DD", `days` from today. Three days is in the future, inside the
 * booking window, and far above the club's shortest hold. */
export function isoDateIn(days: number) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export const SLOT_DATE = isoDateIn(3);

/** The bookings module and the mails a paid space needs, switched on. */
export function enablePaidSpaces() {
  cy.apiLogin(TEST_ACCOUNTS.superAdmin.email, TEST_ACCOUNTS.superAdmin.password);
  cy.request("PUT", `${API}/settings/`, { features: { bookings: true } });
  cy.request("PUT", `${API}/settings/communications`, {
    templates: Object.fromEntries(BOOKING_MAILS.map((k) => [k, true])),
  });
}

/** A pay-to-confirm space charging 10 with one 10:00 slot; yields both ids. */
export function createPaidSpace(
  name: string,
  { methods = ["cash"], capacity = 1 }: { methods?: string[]; capacity?: number } = {}
) {
  cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
  return cy
    .request("POST", `${API}/spaces`, {
      name,
      space_type: "court",
      description: null,
      open_time: "08:00:00",
      close_time: "22:00:00",
      price: 10,
      payment_methods: methods,
    })
    .then((r) => {
      const spaceId = r.body.id as number;
      return cy
        .request("POST", `${API}/spaces/${spaceId}/slots`, {
          slot_date: SLOT_DATE,
          start_time: "10:00:00",
          end_time: "11:00:00",
          capacity,
        })
        .then((s) => cy.wrap({ spaceId, slotId: s.body[0].id as number }));
    });
}

/** Book the slot as `account`; yields the booking. */
export function bookAs(account: Account, slotId: number) {
  cy.apiLogin(account.email, account.password);
  return cy
    .request("POST", `${API}/bookings`, { space_slot_id: slotId })
    .then((r) => cy.wrap(r.body as Booking));
}

/** The receipt of a booking, read from the admin's view of the space. */
export function receiptOf(spaceId: number, bookingId: number) {
  cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
  return cy
    .request(`${API}/spaces/${spaceId}/bookings`)
    .then((r) =>
      cy.wrap(r.body.items.find((b: { id: number }) => b.id === bookingId).receipt_id as number)
    );
}

/** Pay a booking's receipt in cash as the admin, which books it. */
export function payInCash(spaceId: number, bookingId: number) {
  return receiptOf(spaceId, bookingId).then((receiptId) => {
    cy.request("POST", `${API}/receipts/${receiptId}/pay`, { payment_method: "cash" });
  });
}

/**
 * Remove a space a spec built: cancel its bookings, settle what is owed (a
 * refund due blocks the delete), then delete it. Tolerant of anything gone.
 */
export function removeSpace(spaceId: number | undefined) {
  if (spaceId === undefined) return;
  cy.apiLogin(TEST_ACCOUNTS.admin.email, TEST_ACCOUNTS.admin.password);
  cy.request({ url: `${API}/spaces/${spaceId}/bookings?per_page=100`, failOnStatusCode: false }).then(
    (r) => {
      (r.body.items ?? []).forEach((b: { id: number; status: string }) => {
        if (b.status !== "cancelled") {
          cy.request({ method: "DELETE", url: `${API}/bookings/${b.id}`, failOnStatusCode: false });
        }
        cy.request({
          method: "POST",
          url: `${API}/seats/booking/${b.id}/refund-returned`,
          failOnStatusCode: false,
        });
      });
    }
  );
  cy.request({ method: "DELETE", url: `${API}/spaces/${spaceId}?force=true`, failOnStatusCode: false });
}
