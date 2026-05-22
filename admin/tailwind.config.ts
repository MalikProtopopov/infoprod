import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      colors: {
        ink: {
          DEFAULT: '#0b1020',
          soft: '#2a2f45',
        },
      },
      boxShadow: {
        glass: '0 10px 30px -12px rgba(15, 23, 42, 0.18), inset 0 1px 0 rgba(255,255,255,0.6)',
        'glass-lg': '0 24px 50px -18px rgba(15, 23, 42, 0.25), inset 0 1px 0 rgba(255,255,255,0.8)',
        'soft': '0 1px 2px rgba(15,23,42,.04), 0 8px 24px -10px rgba(15,23,42,.08)',
      },
      borderRadius: {
        '2.5xl': '1.25rem',
      },
    },
  },
  plugins: [],
};

export default config;
