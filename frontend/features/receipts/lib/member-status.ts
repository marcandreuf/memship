/**
 * A receipt's status in the words of the member who pays it.
 *
 * The admin labels are the club's: "Cobrado" (collected), "Emitido" (issued),
 * "Devuelto" (returned by the bank). Shown to a member they read backwards —
 * "returned" looks like a refund, and "issued" does not say it is theirs to
 * pay — so the member's own screens use these instead (#591).
 */
export function memberReceiptStatusLabel(
  t: (key: string) => string,
  status: string
): string {
  return t(`receipts.memberStatus.${status}`);
}
