import type { Config } from 'tailwindcss'
export default {
  content: ['./app/**/*.{js,ts,jsx,tsx}', './components/**/*.{js,ts,jsx,tsx}'],
  theme: { extend: { fontFamily: { sans: ['Arial', 'sans-serif'] } } },
  plugins: [],
} satisfies Config
