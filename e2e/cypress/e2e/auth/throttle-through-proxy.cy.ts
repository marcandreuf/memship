// The browser reaches the API through the Next.js proxy, which used to
// drop the caller's address, so every member shared one login bucket
// (#241). It goes through `lib/proxy.ts` now.
//
// `X-Forwarded-For` is set here the way Caddy sets it in front of the
// frontend; with `TRUSTED_PROXY_HOPS=1` the API keys on its rightmost entry.
// The addresses are documentation ranges (RFC 5737), so no bucket another
// spec uses is touched.

const WRONG_PASSWORD = "WrongPassword1!";

function failLogin(ip: string, email: string) {
  return cy.request({
    method: "POST",
    url: "/api/auth/login",
    headers: { "X-Forwarded-For": ip },
    body: { email, password: WRONG_PASSWORD },
    failOnStatusCode: false,
  });
}

describe("Auth throttle through the proxy", () => {
  it("keys the per-address login throttle on the caller, not the frontend", () => {
    // LOGIN_BY_IP allows 20 failures per address and LOGIN_BY_EMAIL 5 per
    // address, so 25 failures from 25 callers on 25 accounts trip nothing —
    // unless every caller lands in the same bucket.
    const run = Date.now();
    for (let i = 1; i <= 25; i++) {
      failLogin(`203.0.113.${i}`, `probe-${run}-${i}@examplee6e3b1.com`)
        .its("status")
        .should("eq", 401);
    }
  });
});
