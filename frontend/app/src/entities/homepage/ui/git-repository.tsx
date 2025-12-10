import { ListBoxItem } from "react-aria-components";

import type { Dropdown } from "@/shared/api/graphql/generated/graphql";
import { focusVisibleStyle } from "@/shared/components/style-rac";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { GENERIC_REPOSITORY_KIND } from "@/shared/config/constants";
import { classNames, getTextColor } from "@/shared/utils/common";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";

export type GitRepositoryData = {
  id: string;
  display_label?: string | null;
  sync_status?: Dropdown | null;
};

export const GitRepositoryItem = ({ repository }: { repository: GitRepositoryData }) => {
  const { id, display_label, sync_status } = repository;

  return (
    <ListBoxItem
      href={getObjectDetailsUrl(GENERIC_REPOSITORY_KIND, id)}
      className={classNames(
        focusVisibleStyle,
        "flex items-center justify-between p-4 text-sm",
        "border border-transparent",
        "hover:bg-neutral-100"
      )}
      textValue={display_label ?? id ?? undefined}
    >
      {display_label}

      {sync_status?.label && (
        <Tooltip enabled={!!sync_status?.description} content={sync_status?.description}>
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
