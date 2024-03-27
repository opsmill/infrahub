/* eslint-disable no-undef */
/** @type {import('tailwindcss').Config} */

const toRgba = (hexCode, opacity = 50) => {
  let hex = hexCode.replace("#", "");

  if (hex.length === 3) {
    hex = `${hex[0]}${hex[0]}${hex[1]}${hex[1]}${hex[2]}${hex[2]}`;
  }

  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);

  return `rgba(${r},${g},${b},${opacity / 100})`;
};

const flattenColorPalette = (obj, sep = "-") =>
  Object.assign(
    {},
    ...(function _flatten(o, p = "") {
      return [].concat(
        ...Object.keys(o).map((k) =>
          typeof o[k] === "object" ? _flatten(o[k], k + sep) : { [p + k]: o[k] }
        )
      );
    })(obj)
  );

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    minHeight: {
      7: "1.75rem", // 28px
      10: "40px",
      48: "12rem" /* 192px */,
      full: "100%",
    },
    extend: {
      fontSize: {
        xxs: "0.625rem",
      },
      colors: {
        "custom-blue": {
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
    require("@tailwindcss/forms"),
    function ({ addUtilities, theme }) {
      const utilities = {
        ".bg-stripes": {
          backgroundImage:
            "linear-gradient(45deg, var(--stripes-color) 12.50%, transparent 12.50%, transparent 50%, var(--stripes-color) 50%, var(--stripes-color) 62.50%, transparent 62.50%, transparent 100%)",
          backgroundSize: "5.66px 5.66px",
        },
      };

      const addColor = (name, color) =>
        (utilities[`.bg-stripes-${name}`] = { "--stripes-color": color });

      const colors = flattenColorPalette(theme("backgroundColor"));
      for (let name in colors) {
        try {
          const [r, g, b, a] = toRgba(colors[name]);
          if (a !== undefined) {
            addColor(name, colors[name]);
          } else {
            addColor(name, `rgba(${r}, ${g}, ${b}, 0.4)`);
          }
        } catch (_) {
          addColor(name, colors[name]);
        }
      }

      addUtilities(utilities);
    },
  ],
  variants: {
    extend: {
      display: ["group-hover"],
    },
  },
};
