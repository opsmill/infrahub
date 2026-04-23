import { useAtomValue } from "jotai";
import { useMemo } from "react";

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
  hasWritePermission: boolean;
}

/**
 * Returns the list of writable CoreRepository instances plus signals for:
 *  - "any repo exists" so the Marketplace page can distinguish "no repos"
 *    from "read-only only".
 *
 * Note: authorization for the install commit lives server-side
 * (POST /api/marketplace/install re-verifies) — we don't gate the UI here
 * because "can update the CoreRepository node" is a different permission
 * from "can git-push". Keeping the UI liberal + server strict.
 */
export function useWritableRepositories(): WritableRepositoriesResult {
  useCurrentBranch();
  useAtomValue(datetimeAtom);

  const { schema: writableSchema } = useSchema(WRITABLE_REPOSITORY_KIND);
  const { schema: readOnlySchema } = useSchema(READ_ONLY_REPOSITORY_KIND);

  const writableQuery = useObjects(
    {
      // schema is non-null when enabled is true
      schema: writableSchema!,
      getAttributesVisible: () => [],
      getRelationshipsVisible: () => [],
    },
    { enabled: !!writableSchema }
  );

  const readOnlyQuery = useObjects(
    {
      schema: readOnlySchema!,
      getAttributesVisible: () => [],
      getRelationshipsVisible: () => [],
    },
    { enabled: !!readOnlySchema }
  );

  const writableRepositories = useMemo<WritableRepositorySummary[]>(() => {
    const items = (writableQuery.data?.pages?.flat() ?? []) as Array<{
      id: string;
      name?: { value?: string };
      default_branch?: { value?: string | null };
    }>;
    return items.map((r) => ({
      id: r.id,
      name: r.name?.value ?? r.id,
      default_branch: r.default_branch?.value ?? null,
    }));
  }, [writableQuery.data]);

  const hasAnyRepository = useMemo(() => {
    const writableCount = (writableQuery.data?.pages?.flat() ?? []).length;
    const readOnlyCount = (readOnlyQuery.data?.pages?.flat() ?? []).length;
    return writableCount + readOnlyCount > 0;
  }, [writableQuery.data, readOnlyQuery.data]);

  const isPending =
    writableQuery.isPending || readOnlyQuery.isPending || !writableSchema || !readOnlySchema;

  return {
    isPending,
    writableRepositories,
    hasAnyRepository,
    hasWritePermission: true,
  };
}
