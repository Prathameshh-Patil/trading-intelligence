import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'

import { ToastProvider } from '@vision-hub/ui'

import { Shell } from '@/components/Shell'
import { LiveProvider } from '@/lib/live'
import { SessionProvider } from '@/lib/session'

import './globals.css'

const sans = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' })
const mono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-jetbrains', display: 'swap' })

export const metadata: Metadata = {
  title: 'Vision Hub — Admin',
  description: 'Approvals, licence keys, tickets and the release switch.',
  robots: { index: false, follow: false },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <SessionProvider>
          <ToastProvider>
            <LiveProvider>
              <Shell>{children}</Shell>
            </LiveProvider>
          </ToastProvider>
        </SessionProvider>
      </body>
    </html>
  )
}
