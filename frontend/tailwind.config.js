/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Satoshi', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        canvas: 'hsl(var(--canvas) / <alpha-value>)',
        surface: 'hsl(var(--surface) / <alpha-value>)',
        raised: 'hsl(var(--raised) / <alpha-value>)',
        line: 'hsl(var(--line) / <alpha-value>)',
        ink: 'hsl(var(--ink) / <alpha-value>)',
        muted: 'hsl(var(--muted) / <alpha-value>)',
        faint: 'hsl(var(--faint) / <alpha-value>)',
        leaf: 'hsl(var(--leaf) / <alpha-value>)',
        leafdim: 'hsl(var(--leaf-dim) / <alpha-value>)',
        sky: 'hsl(var(--sky) / <alpha-value>)',
        amber: 'hsl(var(--amber) / <alpha-value>)',
        rose: 'hsl(var(--rose) / <alpha-value>)',
        violet: 'hsl(var(--violet) / <alpha-value>)',
      },
      borderRadius: { xl: '14px', '2xl': '18px' },
      boxShadow: {
        panel: '0 1px 0 hsl(var(--line) / 0.6), 0 12px 32px -18px rgb(0 0 0 / 0.55)',
        glow: '0 0 0 1px hsl(var(--leaf) / 0.35), 0 0 24px -6px hsl(var(--leaf) / 0.35)',
      },
      keyframes: {
        'fade-up': { '0%': { opacity: 0, transform: 'translateY(6px)' }, '100%': { opacity: 1, transform: 'none' } },
        pulseline: { '0%,100%': { opacity: 0.25 }, '50%': { opacity: 1 } },
      },
      animation: {
        'fade-up': 'fade-up 380ms cubic-bezier(0.22,1,0.36,1) both',
        pulseline: 'pulseline 2.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
