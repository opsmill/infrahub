import { useParams } from "react-router";

import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";

import { ObjectsManager } from "@/entities/nodes/object/ui/objects-manager";
import { ObjectItemsHeader } from "@/entities/nodes/object-header";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

function ObjectItemsPage() {
  const { objectKind } = useParams();

  const { schema } = useSchema(objectKind);

  if (!schema) return <ErrorScreen message={`Schema ${objectKind} not found.`} />;

  return (
    <Content.Card className="flex flex-col">
      <ObjectItemsHeader schema={schema} />

      <ObjectsManager schema={schema} />
    </Content.Card>
  );
}

export const Component = ObjectItemsPage;
