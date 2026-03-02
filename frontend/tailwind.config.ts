import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        accent: "var(--accent)",
        surface: "var(--surface)",
      },
      boxShadow: {
        soft: "0 12px 30px -18px rgba(0, 0, 0, 0.45)",
      },
    },
  },
  plugins: [],
};

export default config;
