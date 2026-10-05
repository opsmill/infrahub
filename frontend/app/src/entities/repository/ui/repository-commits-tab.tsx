import { Spinner } from "@infrahub/ui";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { REPOSITORY_COMMITS_TAB } from "@/entities/repository/domain/model/repository";
import { getPendingImportCount } from "@/entities/repository/domain/rules/get-pending-import-count";
import { useGetRepositoryCommits } from "@/entities/repository/ui/queries/get-repository-commits.query";

export interface RepositoryCommitsTabProps {
  objectKind: string;
  objectId: string;
}

export function RepositoryCommitsTab({ objectKind, objectId }: RepositoryCommitsTabProps) {
  const { isPending, data: pendingImportCount } = useGetRepositoryCommits(
    { repositoryId: objectId },
    {
      select: ({ pages: [firstPage] }) => (firstPage ? getPendingImportCount(firstPage) : null),
    }
  );

  return (
    <LinkTab
      to={getObjectDetailsUrl(objectKind, objectId, undefined, REPOSITORY_COMMITS_TAB)}
      scrollIntoViewOnActive
    >
      Commits
      {isPending ? (
        <Spinner />
      ) : (
        pendingImportCount !== null &&
        pendingImportCount !== undefined && (
          <Badge className="rounded-full font-medium text-subtle">
            {pendingImportCount}
            <span className="sr-only"> pending import</span>
          </Badge>
        )
      )}
    </LinkTab>
  );
}
