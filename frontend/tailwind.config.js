/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        dark: {
          950: '#0a0a0f',
          900: '#0f0f1a',
          800: '#161625',
          700: '#1e1e35',
          600: '#2a2a45',
          500: '#3d3d5c',
        },
        accent: {
          red: '#ff3b5c',
          orange: '#ff7a3d',
          yellow: '#ffc23d',
          green: '#3ddc84',
          blue: '#3d8bff',
          purple: '#a855f7',
        },
      },
    },
  },
  plugins: [],
}
