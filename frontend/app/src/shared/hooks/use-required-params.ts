import { useParams } from "react-router";

/**
 * Read URL params with a runtime guarantee they're present. Throws if any
 * named param is missing — useful when the route config guarantees the param
 * but TypeScript can't prove it.
 */
export function useRequiredParams<K extends string>(...names: K[]): Record<K, string> {
  const params = useParams();
  const result = {} as Record<K, string>;
  for (const name of names) {
    const value = params[name];
    if (value === undefined) {
      throw new Error(`Required URL param "${name}" is missing`);
    }
    result[name] = value;
  }
  return result;
}
