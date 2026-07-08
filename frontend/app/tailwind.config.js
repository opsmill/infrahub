/** @type {import('tailwindcss').Config} */

import animate from "tailwindcss-animate";

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontSize: {
        xxs: "0.625rem",
      },
      colors: {
        // Design-system accent hue. The @infrahub/ui components standardized on
        // Tailwind's `cyan` scale as the single brand-accent token; we remap that
        // scale to OpsMill Blue (#426DB1) so every cyan-* usage (buttons, focus
        // rings, checkboxes, meters, spinners) matches current branding while
        // keeping each component's existing gradient/contrast structure intact.
        cyan: {
          50: "#f1f5fa",
          100: "#dbe4f2",
          200: "#bbcce6",
          300: "#8ca8d4",
          400: "#527cbe",
          500: "#3b629f",
          600: "#335387",
          700: "#2b4773",
          800: "#253e65",
          900: "#213658",
          950: "#152237",
        },
        "custom-blue": {
          1: "#E6ECF5",
          10: "#ADC1E0",
          50: "#3E66A6",
          100: "#4875BB",
          200: "#5F86C4",
          300: "#7697CC",
          400: "#8DA9D5",
          500: "#426DB1",
          600: "#304F81",
          700: "#2B4672",
          800: "#253D64",
          900: "#203556",
        },
        "custom-blue-green": "#0B3981",
        "custom-blue-gray": "#0D2954",
        "custom-gray": "#0B1829",
        "custom-black": "#000000",
        "custom-white": "#FFFFFF",
      },
    },
  },
  plugins: [
    // disable animations in CI to avoid flaky tests.
    // using prefers-reduced-motion and motion-safe was not working when combined with data attributes in tailwind.
    process.env.CI ? () => {} : animate,
  ],
  variants: {
    extend: {
      display: ["group-hover"],
    },
  },
};
