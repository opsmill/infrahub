/**
 * Build the `from_pool` payload for a pending pool allocation, keeping only the
 * fields the API accepts. `prefixlen` is included only when the user entered a
 * concrete number: the nested prefix-length field registers an `undefined` value
 * when untouched, and serializing that as `prefixlen: undefined` is invalid GraphQL.
 */
export const buildFromPoolPayload = (fromPool: {
  id: string;
  prefixlen?: number | null;
}): { id: string; prefixlen?: number } => {
  const { id, prefixlen } = fromPool;
  return { id, ...(typeof prefixlen === "number" && { prefixlen }) };
};
