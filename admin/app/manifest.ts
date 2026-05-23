import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Grammy — админ',
    short_name: 'Grammy',
    description: 'Админ-панель Telegram-бота продажи доступа',
    start_url: '/',
    display: 'standalone',
    orientation: 'portrait',
    background_color: '#0f0a2e',
    theme_color: '#0f0a2e',
    lang: 'ru',
    dir: 'ltr',
    categories: ['business', 'productivity'],
    icons: [
      {
        src: '/icon.svg',
        sizes: 'any',
        type: 'image/svg+xml',
        purpose: 'any',
      },
      {
        src: '/apple-icon',
        sizes: '180x180',
        type: 'image/png',
        purpose: 'maskable',
      },
    ],
  };
}
