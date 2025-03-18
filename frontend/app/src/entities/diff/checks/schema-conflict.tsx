import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";
import { PropertyRow } from "@/entities/schema/ui/styled";
import { Badge } from "@/shared/components/ui/badge";
import { Id } from "@/shared/components/ui/id";
import { useAtomValue } from "jotai";

type SchemaConflictProps = {
  id: string;
  kind: string;
  name: string;
  type: string;
};

export const SchemaConflict = ({ id, kind, name, type }: SchemaConflictProps) => {
  const schemaLabels = useAtomValue(schemaKindLabelState);

  return (
    <div>
      <div className="flex items-center mb-2">
        <Badge className="mr-2">{schemaLabels[kind]}</Badge>

        <Id id={id} kind={kind} />
      </div>

      <div>
        <PropertyRow title="Name" value={name} />
        <PropertyRow title="Type" value={type} />
      </div>
    </div>
  );
};
