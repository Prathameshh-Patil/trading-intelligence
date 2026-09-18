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
  agentRules: false,
}

export default nextConfig
