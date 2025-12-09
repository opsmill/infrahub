import { ListBoxItem } from "react-aria-components";

import type { CoreRepository } from "@/shared/api/graphql/generated/graphql";
import { focusVisibleStyle } from "@/shared/components/style-rac";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames, getTextColor } from "@/shared/utils/common";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";

export const GitRepositoryItem = ({
  id,
  display_label,
  sync_status,
  __typename,
}: CoreRepository) => {
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
