import { Spinner } from "@infrahub/ui";
import { useMatch } from "react-router";

import { Badge } from "@/shared/components/ui/badge";
import { LinkTab } from "@/shared/components/ui/link";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { REPOSITORY_COMMITS_TAB } from "@/entities/repository/domain/model/repository";
import { getPendingImportCount } from "@/entities/repository/domain/rules/get-pending-import-count";
import { useGetRepositoryCommitStatus } from "@/entities/repository/ui/queries/get-repository-commit-status.query";

export interface RepositoryCommitsTabProps {
  objectKind: string;
  objectId: string;
}

export function RepositoryCommitsTab({ objectKind, objectId }: RepositoryCommitsTabProps) {
  const tabUrl = getObjectDetailsUrl(objectKind, objectId, undefined, REPOSITORY_COMMITS_TAB);
  const isCommitLogOpen = !!useMatch({
    path: new URL(tabUrl, window.location.origin).pathname,
    end: true,
  });
  const { isPending, data: status } = useGetRepositoryCommitStatus({
    repositoryId: objectId,
    isCommitLogOpen,
  });
  const pendingImportCount = status ? getPendingImportCount(status) : null;

  return (
    <LinkTab to={tabUrl} scrollIntoViewOnActive>
      Commits
      {isPending ? (
        <Spinner />
      ) : (
        pendingImportCount !== null && (
          <Badge className="rounded-full font-medium text-subtle">
            {pendingImportCount}
            <span className="sr-only"> pending import</span>
          </Badge>
        )
      )}
    </LinkTab>
  );
}
