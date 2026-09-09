import type { NextConfig } from 'next'

/**
 * No server work happens in this app — every dynamic thing it does is a fetch to
 * `services/api`. Keeping it that way means the hosting decision stays open
 * (`plans/team/phase-3-month-two.md` rules out Vercel's Hobby tier for
 * commercial use, and that call has not been remade), so nothing here may grow
 * a dependency on a Node runtime at the edge.
 */
const nextConfig: NextConfig = {
  reactStrictMode: true,

  // Every page here is a client component talking to `services/api` over
  // plain fetch — nothing needs a Node server to render. `output: 'export'`
  // makes `pnpm build` emit static files to `out/`, which is what Cloudflare
  // Pages serves (`plans/team/phase-3-month-two.md` rules out Vercel for this
  // project) and what a plain static host or a drag-and-drop upload needs too.
  output: 'export',

  // Next 16 writes its own AGENTS.md and CLAUDE.md into the app on first run.
  // This repo already has its conventions written down in `plans/` and `docs/`,
  // and a generated file arriving in `git status` unasked is noise at best and
  // contradictory guidance at worst.
  agentRules: false,
}

export default nextConfig
