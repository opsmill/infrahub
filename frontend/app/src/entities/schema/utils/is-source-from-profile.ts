import type { ProfileSchema } from "@/entities/schema/types";

/**
 * Checks if a source typename corresponds to a profile schema.
 * This is used to determine if a field value comes from a profile.
 *
 * @param sourceTypename - The __typename of the source (e.g., "ProfileBuiltinTag")
 * @param profileSchemas - List of profile schemas to check against
 * @returns true if the source typename matches a profile schema's kind
 */
export const isSourceFromProfile = (
  sourceTypename: string | null | undefined,
  profileSchemas: ProfileSchema[]
): boolean => {
  if (!sourceTypename) return false;

  return profileSchemas.some((schema) => schema.kind === sourceTypename);
};
