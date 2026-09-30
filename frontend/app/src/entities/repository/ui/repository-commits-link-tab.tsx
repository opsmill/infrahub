import { LinkTab } from "@/shared/components/ui/link";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { REPOSITORY_COMMITS_TAB } from "@/entities/repository/domain/model/repository";

export interface RepositoryCommitsLinkTabProps {
  objectKind: string;
  objectId: string;
}

export function RepositoryCommitsLinkTab({ objectKind, objectId }: RepositoryCommitsLinkTabProps) {
  return (
    <LinkTab
      to={getObjectDetailsUrl(objectKind, objectId, undefined, REPOSITORY_COMMITS_TAB)}
      scrollIntoViewOnActive
    >
      Commits
    </LinkTab>
  );
}
