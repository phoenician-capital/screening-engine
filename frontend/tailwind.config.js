/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans:    ['Inter', 'system-ui', 'sans-serif'],
        serif:   ['"Playfair Display"', 'Georgia', 'serif'],
        display: ['"Cormorant Garamond"', 'Georgia', 'serif'],
        mono:    ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
      colors: {
        gold: {
          50:  '#fdf9ee',
          100: '#faf0d0',
          200: '#f4e09f',
          300: '#eecb6a',
          400: '#e8b93e',
          500: '#c9961f',
          600: '#a87416',
          700: '#875511',
          800: '#6b4112',
          900: '#583514',
        },
        stone: {
          50:  '#fafaf9',
          100: '#f5f5f4',
          150: '#efefee',
          200: '#e7e5e4',
          300: '#d6d3d1',
          400: '#a8a29e',
          500: '#78716c',
          600: '#57534e',
          700: '#44403c',
          800: '#292524',
          900: '#1c1917',
          950: '#0c0a09',
        },
      },
      boxShadow: {
        'luxury':    '0 1px 3px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.06)',
        'luxury-md': '0 2px 8px rgba(0,0,0,0.06), 0 8px 32px rgba(0,0,0,0.08)',
        'luxury-lg': '0 4px 16px rgba(0,0,0,0.06), 0 16px 48px rgba(0,0,0,0.10)',
        'gold':      '0 0 0 1px rgba(201,150,31,0.3), 0 4px 16px rgba(201,150,31,0.08)',
      },
      borderRadius: {
        'xs': '2px',
      },
      animation: {
        'fade-in':    'fadeIn 0.3s ease-out',
        'slide-up':   'slideUp 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-right':'slideRight 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
        'shimmer':    'shimmer 1.6s ease-in-out infinite',
      },
      keyframes: {
        fadeIn:    { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp:   { from: { opacity: 0, transform: 'translateY(12px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        slideRight:{ from: { opacity: 0, transform: 'translateX(-12px)' }, to: { opacity: 1, transform: 'translateX(0)' } },
        pulseSoft: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.5 } },
        shimmer:   { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
      },
    },
  },
  plugins: [],
}
