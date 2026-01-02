import { type ClassValue, clsx } from "clsx";
import * as R from "remeda";
import { twMerge } from "tailwind-merge";

export const classNames = (...classes: ClassValue[]) => {
  return twMerge(clsx(classes));
};

export const sortByName = <T extends { name: string }>(arr: T[]) =>
  R.sortBy(arr, (x) => x.name.toLowerCase());

export const sortByOrderWeight = <T extends { order_weight?: number | null | undefined }>(
  arr: T[]
) => R.sortBy(arr, (x) => x.order_weight ?? 0);

export const parseJwt = (token: string | null) => {
  if (!token) {
    return;
  }

  try {
    return JSON.parse(atob(token.split(".")[1]!));
  } catch (error) {
    console.error(error);
    return null;
  }
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

export function formatFileSize(bytes: number | undefined | null): string {
  if (bytes === undefined || bytes === null) return "";
  if (bytes === 0) return "0 B";

  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const size = bytes / 1024 ** i;

  return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
}
