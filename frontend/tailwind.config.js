import * as TaildinwFormsPlugin from "@tailwindcss/forms";

/** @type {import('tailwindcss').Config} */
// eslint-disable-next-line no-undef
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {},
  },
  plugins: [TaildinwFormsPlugin],
};
