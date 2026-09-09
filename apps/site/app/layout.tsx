import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'

import { Gate } from '@/components/Gate'
import { SmoothScroll } from '@/components/SmoothScroll'
import { SessionProvider } from '@/lib/session'
import { BRAND } from '@/content/site'

import './globals.css'

const sans = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' })
const mono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-jetbrains', display: 'swap' })

export const metadata: Metadata = {
  title: `${BRAND.name} — order flow for gold futures`,
  description:
    'A candle keeps the open, high, low and close. It does not keep the aggressor side of a single trade. A desktop overlay that reads the raw tape on your own machine.',
}

/**
 * Set `no-motion` before first paint.
 *
 * If this ran in React instead, a reduced-motion visitor would see one frame of
 * the animated state before it was corrected — which is precisely the flash of
 * movement they asked not to have.
 */
const NO_MOTION_SCRIPT = `try{if(matchMedia('(prefers-reduced-motion: reduce)').matches)document.documentElement.classList.add('no-motion')}catch(e){}`

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning is for the class the script below adds before
    // React ever runs. Without it React sees the server's <html> and the
    // client's differ and warns on every load — the warning is correct and the
    // behaviour is intended, which is exactly what this attribute is for.
    <html lang="en" className={`${sans.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: NO_MOTION_SCRIPT }} />
      </head>
      <body>
        <SessionProvider>
          <SmoothScroll />
          <Gate>{children}</Gate>
        </SessionProvider>
      </body>
    </html>
  )
}
