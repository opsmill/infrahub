import type { BranchRepositoriesConnection } from "@/entities/repository/api/get-branch-repositories-from-api";
import type { BranchRepository } from "@/entities/repository/domain/model/branch-repository";
import {
  READONLY_REPOSITORY_KIND,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";

type BranchRepositoryWireNode = NonNullable<
  NonNullable<BranchRepositoriesConnection["edges"][number]>["node"]
>;

interface BranchRepositoryWireConnection {
  edges: ReadonlyArray<{ node?: BranchRepositoryWireNode | null } | null>;
}

export function toBranchRepository(
  node: BranchRepositoryWireNode & { id: string }
): BranchRepository {
  const kind =
    node.__typename === READONLY_REPOSITORY_KIND ? READONLY_REPOSITORY_KIND : REPOSITORY_KIND;

  return {
    id: node.id,
    kind,
    name: node.name?.value || node.display_label || node.id,
    isReadOnly: kind === READONLY_REPOSITORY_KIND,
    commit: node.commit?.value || null,
    syncStatus: {
      value: node.sync_status?.value ?? null,
      label: node.sync_status?.label ?? null,
      color: node.sync_status?.color ?? null,
      description: node.sync_status?.description ?? null,
    },
    operationalStatus: {
      value: node.operational_status?.value ?? null,
      label: node.operational_status?.label ?? null,
    },
  };
}

export function toBranchRepositories(
  connection: BranchRepositoryWireConnection
): BranchRepository[] {
  return connection.edges.flatMap((edge) =>
    edge?.node?.id ? [toBranchRepository({ ...edge.node, id: edge.node.id })] : []
  );
}
