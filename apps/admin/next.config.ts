import type { NextConfig } from 'next'

/**
 * The admin portal is a static export, like the customer site: every dynamic
 * thing it does is a REST call to `services/api`, so it serves from Cloudflare
 * Pages (or any static host) on its own origin.
 */
const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: 'export',
  // Workspace packages are consumed as TypeScript source.
  transpilePackages: ['@vision-hub/contracts', '@vision-hub/ui'],
  // Browsers scope cookies by host, not by port, so `localhost:3000` (site)
  // and `localhost:3001` (admin) share one refresh cookie in development and
  // signing in to one signs the other in too. Run the portal against
  // 127.0.0.1 instead -- `pnpm dev:admin` with
  // NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000, opened at 127.0.0.1:3001 --
  // which is a different host with its own jar, and same-site with the API
  // so the refresh cookie still travels. Next has to be told to serve dev
  // assets to that host.
  allowedDevOrigins: ['127.0.0.1'],
  agentRules: false,
}

export default nextConfig
