import { Clipboard } from "@/shared/components/buttons/clipboard";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Badge } from "@/shared/components/ui/badge";

import { NODE_OBJECT } from "@/entities/nodes/object/domain/model/object-kinds";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { useNodeLabel } from "@/entities/nodes/object/ui/queries/get-display-label.query";

type tId = {
  id: string;
  kind?: string;
  branch?: string | null;
  date?: Date | null;
  preventCopy?: boolean;
};

export const Id = ({ id, kind = NODE_OBJECT, preventCopy, branch, date }: tId) => {
  const {
    isPending,
    error,
    data: object,
  } = useNodeLabel({
    objectId: id,
    kind,
    branch,
    atDate: date,
  });

  if (isPending) {
    return <LoadingIndicator />;
  }

  if (error || !getNodeLabel(object)) {
    return <Badge variant="white">Name not found</Badge>;
  }

  return (
    <Badge variant="white" className="font-medium">
      {getNodeLabel(object)}

      {!preventCopy && (
        <Clipboard
          value={id}
          alert="ID copied!"
          tooltip="Copy ID"
          className="ml-2 rounded-full p-1"
        />
      )}
    </Badge>
  );
};
