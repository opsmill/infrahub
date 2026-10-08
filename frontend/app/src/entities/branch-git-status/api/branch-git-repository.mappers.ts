import type { BranchGitRepositoriesConnection } from "@/entities/branch-git-status/api/get-branch-git-repositories-from-api";
import type { BranchGitRepositoryPage } from "@/entities/branch-git-status/domain/model/branch-git-repository";
import { READONLY_REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";

export function toBranchGitRepositoryPage(
  connection: BranchGitRepositoriesConnection
): BranchGitRepositoryPage {
  return {
    repositories: connection.edges.flatMap(({ node }) =>
      node?.id
        ? [
            {
              id: node.id,
              name: node.name?.value || node.id,
              kind: node.__typename,
              isReadOnly: node.__typename === READONLY_REPOSITORY_KIND,
            },
          ]
        : []
    ),
    count: connection.count,
  };
}
