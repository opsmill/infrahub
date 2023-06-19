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
