import { GENERIC_REPOSITORY_KIND } from "@/config/constants";

import type { CoreRepository } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { Link } from "@/shared/components/ui/link";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames, getTextColor } from "@/shared/utils/common";

export const GitRepositoryItem = ({ id, display_label, sync_status }: CoreRepository) => {
  return (
    <div className="flex items-center justify-between p-4 text-sm">
      <Link
        className="flex items-center gap-1"
        to={constructPath(`objects/${GENERIC_REPOSITORY_KIND}/${id}`)}
      >
        {display_label}
      </Link>
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
