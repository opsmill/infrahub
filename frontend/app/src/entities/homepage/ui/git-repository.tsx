import type { CoreRepository } from "@/shared/api/graphql/generated/graphql";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames, getTextColor } from "@/shared/utils/common";

export const GitRepositoryItem = ({ display_label, sync_status }: CoreRepository) => {
  return (
    <div className="flex items-center justify-between p-4">
      <div>{display_label}</div>
      <Tooltip enabled={!!sync_status?.description} content={sync_status?.description}>
        <div
          className={classNames("rounded-full px-3 py-1.5")}
          style={
            sync_status?.color
              ? { backgroundColor: sync_status?.color, color: getTextColor(sync_status?.color) }
              : undefined
          }
        >
          {sync_status?.label}
        </div>
      </Tooltip>
    </div>
  );
};
