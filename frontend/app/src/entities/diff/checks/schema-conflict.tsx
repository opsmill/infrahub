import { PropertyRow } from "@/entities/schema/ui/styled";
import { Badge } from "@/shared/components/ui/badge";
import { Id } from "@/shared/components/ui/id";

type SchemaConflictProps = {
  id: string;
  kind: string;
  name: string;
  type: string;
};

export const SchemaConflict = ({ id, kind, name, type }: SchemaConflictProps) => {
  return (
    <div>
      <div className="flex items-center mb-2">
        <Badge className="mr-2">{kind}</Badge>

        <Id id={id} kind={kind} />
      </div>

      <div>
        <PropertyRow title="Name" value={name} />
        <PropertyRow title="Type" value={type} />
      </div>
    </div>
  );
};
