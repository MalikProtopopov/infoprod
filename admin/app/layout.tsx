import './globals.css';
import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000';

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: 'Grammy — админ',
    template: '%s · Grammy',
  },
  description:
    'Админ-панель Telegram-бота продажи доступа: воронки, аналитика, платежи.',
  applicationName: 'Grammy',
  generator: 'Next.js',
  referrer: 'strict-origin-when-cross-origin',
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  robots: {
    index: false,
    follow: false,
    nocache: true,
    googleBot: {
      index: false,
      follow: false,
      noimageindex: true,
      'max-snippet': -1,
      'max-image-preview': 'none',
    },
  },
  openGraph: {
    type: 'website',
    locale: 'ru_RU',
    siteName: 'Grammy',
    title: 'Grammy — админ',
    description:
      'Админ-панель Telegram-бота продажи доступа: воронки, аналитика, платежи.',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Grammy — админ',
    description:
      'Админ-панель Telegram-бота продажи доступа: воронки, аналитика, платежи.',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  colorScheme: 'light dark',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f4f6fb' },
    { media: '(prefers-color-scheme: dark)', color: '#0f0a2e' },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body className="min-h-screen antialiased font-sans relative overflow-x-hidden">
        {/* Декоративные блобы фона */}
        <div aria-hidden className="pointer-events-none fixed inset-0 -z-10">
          <div className="absolute -top-32 -left-32 w-[40rem] h-[40rem] rounded-full bg-indigo-400/25 blur-3xl anim-blob-1" />
          <div className="absolute -top-40 right-[-10rem] w-[36rem] h-[36rem] rounded-full bg-rose-400/20 blur-3xl anim-blob-2" />
          <div className="absolute bottom-[-12rem] left-1/3 w-[42rem] h-[42rem] rounded-full bg-teal-300/20 blur-3xl anim-blob-3" />
        </div>
        {children}
      </body>
    </html>
  );
}
