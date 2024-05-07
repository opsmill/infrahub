import { QSP } from "../config/qsp";

export const fetchUrl = async (url: string, payload?: any) => {
  const newPayload = {
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...payload?.headers,
    },
    method: payload?.method ?? "GET",
    ...(payload?.method === "POST"
      ? {
          body: payload?.body ?? "",
        }
      : {}),
  };

  const rawResponse = await fetch(url, newPayload);

  return rawResponse?.json();
};

const read = async (reader: any): Promise<string> => {
  const result = await reader.read();

  const currentValue = new TextDecoder().decode(result.value);

  if (result.done) {
    return currentValue;
  }

  const nextResult = await read(reader);

  return `${currentValue} ${nextResult}`;
};

export const fetchStream = async (url: string, payload?: any) => {
  const response = await fetch(url, payload);

  if (!response.ok) {
    return "No file content";
  }

  const stream = response.body; // ReadableStream object
  const reader = stream?.getReader();

  const result = await read(reader); // Returns a promise that resolves with a chunk of data

  return result;
};

const QSP_TO_INCLUDE = [QSP.BRANCH, QSP.DATETIME];

export type overrideQueryParams = {
  name: string;
  value?: string | null;
  exclude?: boolean;
};

// Construct link with path that contains all QSP
export const constructPath = (
  path: string,
  overrideParams?: overrideQueryParams[],
  preserveQspLib: string[] = []
) => {
  const currentURLSearchParams = getCurrentQsp();
  const newURLSearchParams = new URLSearchParams();

  // Remove some QSP if not needed to be forwarded
  [...QSP_TO_INCLUDE, ...preserveQspLib].forEach((qsp) => {
    const paramValue = currentURLSearchParams.get(qsp);
    if (paramValue) newURLSearchParams.set(qsp, paramValue);
  });

  overrideParams?.forEach(({ name, value, exclude }) => {
    if (exclude) {
      newURLSearchParams.delete(name);
    } else if (value) {
      newURLSearchParams.set(name, value);
    }
  });

  // Prevent having a trailing '?'
  if (!newURLSearchParams.toString()) return path;

  return `${path}?${newURLSearchParams.toString()}`;
};

export const getCurrentQsp = () => new URL(window.location.href).searchParams;

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

  return setSearchParams(newParams);
};

export const getUrlWithQsp = (url: string, options: any[]) => {
  const qsp = new URLSearchParams(options);

  if (url.includes("?")) {
    // If the url already contains some QSP
    return `${url}${options.length ? `&${qsp.toString()}` : ""}`;
  }

  return `${url}${options.length ? `?${qsp.toString()}` : ""}`;
};
