import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./lib/i18n/request.ts");

// Mirrors the `header` block in the repo-root Caddyfile. Caddy is the edge in a
// real deployment and its values win, but `next dev`, `next start` and any
// install that fronts this with something other than Caddy never see that file
// — and the /api/uploads proxy, which hands back member photos and attachments,
// is served from here.
const SECURITY_HEADERS = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
  async rewrites() {
    // SSO is a full browser redirect, so the browser — not the server — has to
    // reach the backend. Deployments put both behind Caddy on one origin and it
    // routes /api/v1/* before Next sees it; this rewrite is what makes the same
    // relative URL work in local dev, where the API is on its own port.
    return [
      {
        source: "/api/v1/auth/oauth/:path*",
        destination: `${
          process.env.API_BASE_URL || "http://localhost:8003"
        }/api/v1/auth/oauth/:path*`,
      },
    ];
  },
};

export default withNextIntl(nextConfig);
