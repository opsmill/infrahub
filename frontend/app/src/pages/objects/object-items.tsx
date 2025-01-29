import { ObjectsTableManager } from "@/entities/nodes/object/ui/objects-table/objects-table-manager";
import { useSchema } from "@/entities/schema/hooks/useSchema";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { useParams } from "react-router";

export function ObjectItemsPage() {
  const { objectKind } = useParams();

  const { schema } = useSchema(objectKind);

  if (!schema) return <ErrorScreen message={`Object ${objectKind} not found.`} />;

  return <ObjectsTableManager schema={schema} />;
}

export const Component = ObjectItemsPage;
