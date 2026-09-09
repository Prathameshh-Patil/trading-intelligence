import Link from 'next/link'

import { Mark } from './ui'
import { BRAND, RISK_LINE } from '@/content/site'

export function Footer() {
  return (
    <footer className="relative mt-10 overflow-hidden border-t border-white/[0.06]">
      <div className="aura aura-violet -top-40 left-1/2 h-72 w-[42rem] -translate-x-1/2 opacity-50" />

      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-6 px-6 py-14 text-[13px] text-faint">
        <div className="flex items-center gap-2.5 font-semibold text-ink">
          <Mark size={26} />
          {BRAND.name}
        </div>

        <div className="flex flex-wrap gap-7">
          {/* The refund policy is one click from every page, deliberately. */}
          <Link href="/policy" className="transition hover:text-ink">Terms, refunds &amp; privacy</Link>
          <Link href="/support" className="transition hover:text-ink">Support</Link>
          <Link href="/contact" className="transition hover:text-ink">Contact</Link>
        </div>

        <span className="max-w-[38ch] leading-relaxed">
          © 2026 {BRAND.name}. {RISK_LINE}
        </span>
      </div>
    </footer>
  )
}
