import { QSP } from "@/shared/config/qsp";

import { ACCESS_TOKEN_KEY } from "@/entities/authentication/constants";

export const fetchUrl = async (url: string, payload?: RequestInit) => {
  const localToken = localStorage.getItem(ACCESS_TOKEN_KEY);

  const newPayload = {
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(localToken ? { authorization: `Bearer ${localToken}` } : {}),
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

  if (path.includes("?")) {
    return `${path}&${newURLSearchParams.toString()}`;
  }

  return `${path}?${newURLSearchParams.toString()}`;
};

export const getCurrentQsp = () => new URL(window.location.href).searchParams;
