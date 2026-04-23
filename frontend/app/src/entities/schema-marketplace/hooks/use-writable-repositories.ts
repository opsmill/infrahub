import { useAtomValue } from "jotai";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useObjects } from "@/entities/nodes/object/ui/queries/get-objects.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

const WRITABLE_REPOSITORY_KIND = "CoreRepository";
const READ_ONLY_REPOSITORY_KIND = "CoreReadOnlyRepository";

export interface WritableRepositorySummary {
  id: string;
  name: string;
  default_branch: string | null;
}

export interface WritableRepositoriesResult {
  isPending: boolean;
  writableRepositories: WritableRepositorySummary[];
  hasAnyRepository: boolean;
}

/**
 * Returns the list of writable CoreRepository instances plus a signal for
 * "any repo exists" so the Marketplace page can distinguish "no repos" from
 * "read-only only".
 *
 * Authorization for the install commit lives server-side
 * (POST /api/marketplace/install enforces MANAGE_SCHEMA / MANAGE_REPOSITORIES
 * via the PermissionManager). The hook returns all writable repos — the server
 * is the source of truth on whether the user can actually commit.
 */
export function useWritableRepositories(): WritableRepositoriesResult {
  // Subscribe to branch and datetime changes so `useObjects` below re-runs
  // when the user switches branches or the "view as-of" time changes. The
  // return values aren't used directly — the subscriptions exist solely to
  // trigger a re-render of this hook, which drives the query invalidation
  // inside `useObjects` via its internal dependency tracking.
  useCurrentBranch();
  useAtomValue(datetimeAtom);

  const { schema: writableSchema } = useSchema(WRITABLE_REPOSITORY_KIND);
  const { schema: readOnlySchema } = useSchema(READ_ONLY_REPOSITORY_KIND);

  const writableQuery = useObjects(
    {
      // schema is non-null when enabled is true
      schema: writableSchema!,
      // Request only the attributes we actually render (name for the dropdown
      // label, default_branch for seeding the install form). Empty array would
      // return nodes without any attributes populated, which is why the
      // repo picker was showing UUIDs.
      getAttributesVisible: (attributes) =>
        attributes.filter(({ name }) => name === "name" || name === "default_branch"),
      getRelationshipsVisible: () => [],
    },
    { enabled: !!writableSchema }
  );

  const readOnlyQuery = useObjects(
    {
      schema: readOnlySchema!,
      getAttributesVisible: (attributes) => attributes.filter(({ name }) => name === "name"),
      getRelationshipsVisible: () => [],
    },
    { enabled: !!readOnlySchema }
  );

  const writableItems = (writableQuery.data?.pages?.flat() ?? []) as Array<{
    id: string;
    name?: { value?: string };
    default_branch?: { value?: string | null };
  }>;
  const writableRepositories: WritableRepositorySummary[] = writableItems.map((r) => ({
    id: r.id,
    name: r.name?.value ?? r.id,
    default_branch: r.default_branch?.value ?? null,
  }));

  const readOnlyCount = (readOnlyQuery.data?.pages?.flat() ?? []).length;
  const hasAnyRepository = writableRepositories.length + readOnlyCount > 0;

  const isPending =
    writableQuery.isPending || readOnlyQuery.isPending || !writableSchema || !readOnlySchema;

  return {
    isPending,
    writableRepositories,
    hasAnyRepository,
  };
}
