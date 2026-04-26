import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          base: "#0f172a",
          surface: "#1e293b",
          subtle: "#334155",
        },
        accent: {
          DEFAULT: "#06b6d4",
          fg: "#082f49",
        },
        tier: {
          hobby: "#a78bfa",
          personal: "#34d399",
          mvp: "#06b6d4",
          startup: "#f59e0b",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
        mono: [
          "var(--font-jetbrains-mono)",
          "JetBrains Mono",
          "ui-monospace",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
