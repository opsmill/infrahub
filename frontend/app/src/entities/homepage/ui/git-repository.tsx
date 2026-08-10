import { Tooltip } from "@infrahub/ui";
import { ListBoxItem } from "react-aria-components";

import type { Dropdown } from "@/shared/api/graphql/generated/types";
import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
<<<<<<< HEAD
import { classNames, getTextColor } from "@/shared/utils/common";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { GENERIC_REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
=======
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames, getTextColor } from "@/shared/utils/common";

import type { NodeCore } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
>>>>>>> stable

export interface GitRepositoryData extends NodeCore {
  sync_status?: Dropdown | null;
}

export const GitRepositoryItem = ({ repository }: { repository: GitRepositoryData }) => {
  const { id, __typename, display_label, sync_status } = repository;

  return (
    <ListBoxItem
      href={getObjectDetailsUrl(__typename, id)}
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
