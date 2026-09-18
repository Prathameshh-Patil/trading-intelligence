import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'

import { ToastProvider } from '@vision-hub/ui'

import { Gate } from '@/components/Gate'
import { SmoothScroll } from '@/components/SmoothScroll'
import { BRAND } from '@/content/site'
import { LiveProvider } from '@/lib/live'
import { SessionProvider } from '@/lib/session'

import './globals.css'

const sans = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' })
const mono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-jetbrains', display: 'swap' })

export const metadata: Metadata = {
  title: {
    default: `${BRAND.name} — ${BRAND.tagline.toLowerCase()}`,
    template: `%s — ${BRAND.name}`,
  },
  description:
    'A candle keeps the open, high, low and close. It does not keep the aggressor side of a single trade. A desktop overlay that reads the raw tape on your own machine.',
  icons: { icon: '/favicon.svg' },
  openGraph: {
    title: `${BRAND.name} — ${BRAND.tagline}`,
    description: 'Same candle. Opposite order flow. A desktop overlay that reads the raw tape on your own machine.',
    siteName: BRAND.name,
    images: ['/og.png'],
  },
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
          <ToastProvider>
            <LiveProvider>
              <SmoothScroll />
              <Gate>{children}</Gate>
            </LiveProvider>
          </ToastProvider>
        </SessionProvider>
      </body>
    </html>
  )
}
