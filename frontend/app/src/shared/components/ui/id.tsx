import { Clipboard } from "@/shared/components/buttons/clipboard";
import { BadgeCircle, CIRCLE_BADGE_TYPES } from "@/shared/components/display/badge-circle";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { NODE_OBJECT } from "@/shared/config/constants";

import { useNodeLabel } from "@/entities/nodes/object/ui/queries/get-display-label.query";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";

type tId = {
  id: string;
  kind?: string;
  branch?: string | null;
  preventCopy?: boolean;
};

export const Id = ({ id, kind = NODE_OBJECT, preventCopy, branch }: tId) => {
  const { isPending, error, data: object } = useNodeLabel({ objectId: id, kind, branch });

  if (isPending) {
    return <LoadingIndicator />;
  }

  if (error || !getNodeLabel(object)) {
    return <BadgeCircle type={CIRCLE_BADGE_TYPES.LIGHT}>Name not found</BadgeCircle>;
  }

  return (
    <BadgeCircle type={CIRCLE_BADGE_TYPES.LIGHT}>
      {getNodeLabel(object)}

      {!preventCopy && (
        <Clipboard
          value={id}
          alert="ID copied!"
          tooltip="Copy ID"
          className="ml-2 rounded-full p-1"
        />
      )}
    </BadgeCircle>
  );
};
