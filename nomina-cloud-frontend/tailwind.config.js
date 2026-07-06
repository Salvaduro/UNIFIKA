/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'unifika-primary': {
          DEFAULT: '#146a85',
          light: '#1b8ea6',
          dark: '#0e4a5d',
        },
        'unifika-accent': {
          DEFAULT: '#babf15',
          hover: '#9a9e10',
        }
      }
    },
  },
  plugins: [],
}

