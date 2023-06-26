/* eslint-disable no-undef */
/** @type {import('tailwindcss').Config} */

module.exports = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        "custom-blue": "#0B97BB",
        "custom-blue-green": "#0B6581",
        "custom-dark-gray": "#0D3F54",
        "custom-gray": "#0B1829",
        "custom-black": "#000000",
        "custom-white": "#FFFFFF",
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};
