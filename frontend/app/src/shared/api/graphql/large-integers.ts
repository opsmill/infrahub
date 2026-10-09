import { retryingFetch } from "@/shared/api/rate-limit/retrying-fetch";

// String literals are matched as whole tokens so that digits inside them are never rewritten.
const STRING_OR_LONG_INTEGER = /"(?:[^"\\]|\\.)*"|(?<![\w.+-])-?\d{16,}(?![\d.eE])/g;

/** Turns every integer literal of a JSON text that a JavaScript number cannot hold exactly into a string. */
export function quoteLargeIntegers(json: string): string {
  return json.replace(STRING_OR_LONG_INTEGER, (token) =>
    token.startsWith('"') || Number.isSafeInteger(Number(token)) ? token : `"${token}"`
  );
}

export const fetchKeepingLargeIntegersExact: typeof fetch = async (input, init) => {
  const response = await retryingFetch(input, init);
  const body = quoteLargeIntegers(await response.text());

  return new Response(body, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });
};
