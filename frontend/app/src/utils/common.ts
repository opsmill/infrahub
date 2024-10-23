import { IModelSchema, iGenericSchema } from "@/state/atoms/schema.atom";
import { type ClassValue, clsx } from "clsx";
import * as R from "ramda";
import { twMerge } from "tailwind-merge";

export const classNames = (...classes: ClassValue[]) => {
  return twMerge(clsx(classes));
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

const DEFAULT_DEBOUNCE = 300;

export function debounce<T extends (...args: any[]) => any>(
  func: T,
  delay: number = DEFAULT_DEBOUNCE
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return function (this: ThisParameterType<T>, ...args: Parameters<T>): void {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    timeoutId = setTimeout(() => {
      func.apply(this, args);
    }, delay);
  };
}

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

// Raise TS error when not every case is handled
export function warnUnexpectedType(x: never) {
  console.warn(`unexpected type ${x}`);
}

export function isGeneric(schema: IModelSchema): schema is iGenericSchema {
  return "used_by" in schema;
}
