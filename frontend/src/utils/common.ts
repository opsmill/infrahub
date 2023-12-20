import * as R from "ramda";

export const classNames = (...classes: string[]) => {
  // Replcaa tabs and spaces to have multiline in code, but one ligne in output
  return classes
    .filter(Boolean)
    .join(" ")
    .replaceAll(/(\t|\s)+/g, " ")
    .trim();
};

export const objectToString = (object: any) =>
  Object.entries(object)
    .map(([key, value]) => {
      switch (typeof value) {
        // Add quotes for string
        case "string": {
          return `${key}:"${value}"`;
        }
        default: {
          return `${key}:${value}`;
        }
      }
    })
    .join(",");

export const sortByName = R.sortBy(R.compose(R.toLower, R.prop("name")));

export const sortByOrderWeight = R.sortBy(R.compose(R.prop("order_weight")));

export const parseJwt = (token: string | null) => {
  if (!token) {
    return;
  }

  try {
    return JSON.parse(atob(token.split(".")[1]));
  } catch (e) {
    return null;
  }
};

export const encodeJwt = (data: any): string => {
  // Add "." to be decoded by parseJwt
  return `.${btoa(JSON.stringify(data))}`;
};

const DEFAULT_DEBOUNCE = 1000;

export const debounce = (func: any, wait = DEFAULT_DEBOUNCE, immediate?: boolean) => {
  let timeout: any;
  return function executedFunction(this: any) {
    const context = this;
    // eslint-disable-next-line prefer-rest-params
    const args = arguments;
    const later = () => {
      timeout = null;
      if (!immediate) func.apply(context, args);
    };
    const callNow = immediate && !timeout;
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
    if (callNow) func.apply(context, args);
  };
};

// https://fontawesomeicons.com/fa/react-js-change-text-color-based-on-brightness-background
const calculateBrightness = (color: string) => {
  const hex = color.replace("#", "");
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  return brightness;
};

export const getTextColor = (background?: string) => {
  if (!background) return "black";

  const isDarkBackground = calculateBrightness(background) < 128;

  return isDarkBackground ? "white" : "black";
};
