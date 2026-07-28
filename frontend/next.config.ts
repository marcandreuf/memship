import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./lib/i18n/request.ts");

const nextConfig: NextConfig = {
  output: "standalone",
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
