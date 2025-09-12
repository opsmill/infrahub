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
        "custom-blue": {
          1: "#E4F3F7",
          10: "#a7d9e6",
          50: "#23a1c1",
          100: "#3babc8",
          200: "#54b6cf",
          300: "#6cc0d6",
          400: "#85cbdd",
          500: "#0B97BB",
          600: "#0987a8",
          700: "#087895",
          800: "#076982",
          900: "#065a70",
        },
        "custom-blue-green": "#0B6581",
        "custom-blue-gray": "#0D3F54",
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
