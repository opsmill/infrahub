import { QSP } from "../config/qsp";

export const fetchUrl = async (url: string, payload?: any) => {
  const rawResponse = await fetch(url, payload);
  return rawResponse?.json();
};

const QSP_TO_INCLUDE = [QSP.BRANCH];

// Construct link with path that contains all QSP
export const constructPath = (path: string) => {
  const { href } = window.location;

  const url = new URL(href);

  const { searchParams } = url;

  // Get QSP as [ [ key, value ], ... ]
  const params = Array.from(searchParams)
    .filter(
      ([k]) => QSP_TO_INCLUDE.includes(k) // Remove some QSP if not needed to be forwarded
    )
    .filter(
      ([k]) => !path.includes(k) // If a QSP is already in the path, then we don't override it
    );

  // Construct the new params as "?key=value&..."
  const newParams = params.length
    ? params.reduce(
        (acc, [k, v], index) => `${acc}${k}=${v}${index === params.length - 1 ? "" : "&"}`,
        "?"
      )
    : "";

  return `${path}${newParams}`;
};

// Update a QSP in the URL (add, update or remove it)
export const updateQsp = (qsp: string, newValue: string, setSearchParams: Function) => {
  const { href } = window.location;

  const url = new URL(href);

  const { searchParams } = url;

  // Get QSP as [ [ key, value ], ... ]
  const params = [...Array.from(searchParams), [qsp, newValue]];

  // Construct the new params as { [name]: value }
  const newParams = params.reduce(
    (acc, [k, v]) => ({
      ...acc,
      [k]: v,
    }),
    {}
  );

  console.log("newParams: ", newParams);
  return setSearchParams(newParams);
};
