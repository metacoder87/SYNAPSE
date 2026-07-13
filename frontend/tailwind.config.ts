import type { Config } from "tailwindcss";

/**
 * SYNAPSE cyberpunk theme tokens (PRD §2):
 * - Background: #0a0a0a
 * - Electric cyan: #06b6d4 | Neon magenta: #db2777
 * - Glow borders via box-shadow utilities
 * - Space Mono typography
 */
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        void: "#0a0a0a",
        surface: "#111113",
        cyber: {
          cyan: "#06b6d4",
          magenta: "#db2777",
        },
      },
      fontFamily: {
        mono: ['"Space Mono"', "monospace"],
      },
      boxShadow: {
        "glow-cyan": "0 0 8px #06b6d4, inset 0 0 4px rgba(6,182,212,0.3)",
        "glow-magenta": "0 0 8px #db2777, inset 0 0 4px rgba(219,39,119,0.3)",
      },
    },
  },
  plugins: [],
};
export default config;
