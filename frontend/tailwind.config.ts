import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: { 950: "#0b1b34", 900: "#10264a", 800: "#183461", 700: "#24477f" },
        brand: { 50: "#eef6ff", 100: "#d9eaff", 500: "#1d6fe0", 600: "#175cc0", 700: "#134a9a" },
        teal: { 500: "#0d9488", 600: "#0f766e" },
      },
      boxShadow: { card: "0 1px 2px rgba(16,38,74,.06), 0 4px 14px rgba(16,38,74,.05)" },
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"] },
    },
  },
  plugins: [],
};
export default config;
