import * as z from "zod";

// A URL query-string filter. `name` is a plain string: schema filters use
// `field__operator`, plus control names like "order" and entity-specific
// availability filters — validating those shapes is the caller's job, not the
// generic filter primitive's.
export const FilterSchema = z.array(
  z.object({
    name: z.string(),
    value: z.any(),
  })
);

export type Filter = z.infer<typeof FilterSchema>[number];
