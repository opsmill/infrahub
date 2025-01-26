import { ObjectsTable } from "@/entities/nodes/object/ui/objects-table/objects-table";
import { useSchema } from "@/entities/schema/hooks/useSchema";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { useParams } from "react-router-dom";

export function ObjectItemsPage() {
  const { objectKind } = useParams();

  const { schema } = useSchema(objectKind);
  if (!schema) return <ErrorScreen message={`Object ${objectKind} not found.`} />;

  return <ObjectsTable schema={schema} />;
}

export const Component = ObjectItemsPage;
