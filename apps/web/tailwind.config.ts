import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primo brand palette — tune later with the real brand
        brand: {
          DEFAULT: "#3400D1",
          accent: "#FF007A",
          highlight: "#FFD600",
        },
      },
    },
  },
  plugins: [],
};

export default config;
