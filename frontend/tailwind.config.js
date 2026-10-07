/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: "var(--paper)",
        ink: "var(--ink)",
        blood: "var(--blood)",
        "blood-bright": "var(--blood-bright)",
        line: "var(--line)",
        success: "var(--success)",
        muted: "var(--muted)",
      },
      fontFamily: {
        serif: ['"Source Serif 4"', 'Lora', 'Georgia', 'serif'],
        sans: ['"IBM Plex Sans"', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
