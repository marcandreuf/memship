// The browser reaches the API through the Next.js proxy, which used to
// forward neither the caller's address in nor the API's `Retry-After` out.
// Every member then shared one login bucket (#241) and a throttled one was
// never told how long to wait (#243). Both go through `lib/proxy.ts` now.
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

  it("tells a throttled caller how long to wait", () => {
    // One caller, 21 failures on 21 accounts: the 21st exceeds LOGIN_BY_IP.
    // A fresh address per run so a retry within the window starts clean.
    const run = Date.now();
    const ip = `198.51.100.${1 + (run % 250)}`;
    for (let i = 1; i <= 21; i++) {
      failLogin(ip, `spray-${run}-${i}@examplee6e3b1.com`).as(`attempt${i}`);
    }
    cy.get("@attempt21").then((res) => {
      const response = res as unknown as Cypress.Response<unknown>;
      expect(response.status).to.eq(429);
      expect(Number(response.headers["retry-after"])).to.be.greaterThan(0);
    });
  });
});
