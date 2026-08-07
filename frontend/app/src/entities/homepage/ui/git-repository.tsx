import { Tooltip } from "@infrahub/ui";
import { ListBoxItem } from "react-aria-components";

import type { Dropdown } from "@/shared/api/graphql/generated/types";
import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { classNames, getTextColor } from "@/shared/utils/common";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { GENERIC_REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";

export type GitRepositoryData = {
  id: string;
  __typename: string;
  display_label?: string | null;
  sync_status?: Dropdown | null;
};

export const GitRepositoryItem = ({ repository }: { repository: GitRepositoryData }) => {
  const { id, __typename, display_label, sync_status } = repository;

  return (
    <ListBoxItem
      // Link to the object's concrete kind (e.g. CoreRepository / CoreReadOnlyRepository)
      // rather than the generic kind, so the details/edit routes resolve the schema that
      // actually exposes its fields. Falls back to the generic kind if __typename is absent.
      href={getObjectDetailsUrl(__typename ?? GENERIC_REPOSITORY_KIND, id)}
      className={classNames(
        focusVisibleStyle,
        "flex items-center justify-between p-4 text-sm",
        "border border-transparent",
        "hover:bg-neutral-100"
      )}
      textValue={display_label ?? id}
    >
      {display_label}

      {sync_status?.label && (
        <Tooltip message={sync_status?.description} nonInteractiveTrigger>
          <div
            className={classNames("rounded-full px-3 py-1.5 text-xs")}
            style={
              sync_status?.color
                ? { backgroundColor: sync_status?.color, color: getTextColor(sync_status?.color) }
                : undefined
            }
          >
            {sync_status.label}
          </div>
        </Tooltip>
      )}
    </ListBoxItem>
  );
};
