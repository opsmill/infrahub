import { useAtomValue } from "jotai";

import { Badge } from "@/shared/components/ui/badge";
import { Id } from "@/shared/components/ui/id";

import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";

type SchemaConflictProps = {
  id: string;
  kind: string;
  name: string;
  type: string;
};

export const SchemaConflict = ({ id, kind, name, type }: SchemaConflictProps) => {
  const schemaLabels = useAtomValue(schemaKindLabelState);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center">
        <Badge className="mr-2">{schemaLabels[kind]}</Badge>

        <Id id={id} kind={kind} />
      </div>

      <div className="flex">
        <div className="min-w-40 font-semibold text-gray-500">Name</div>
        <div>{name}</div>
      </div>

      <div className="flex">
        <div className="min-w-40 font-semibold text-gray-500">Type</div>
        <div>{type}</div>
      </div>
    </div>
  );
};
