import type { NodeCore } from "@/entities/nodes/types";

// ProfileData represents profile data from the API.
// Dynamic fields (attributes & relationships) are accessed by name and narrowed at the call site,
// so the index signature uses `unknown` to avoid conflicts with NodeCore properties.
export type ProfileData = NodeCore & {
  profile_priority?: { value: number | null };
  [key: string]: unknown;
};
