import { queryClient } from "@/shared/api/rest/client";
import ObjectEditSlideOverTrigger from "@/shared/components/form/object-edit-slide-over-trigger";
import { Badge } from "@/shared/components/ui/badge";
import { Card, CardWithBorder } from "@/shared/components/ui/card";

import { ObjectDataDisplay } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-display";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeObjectWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

type GraphqlQueryDetailsCardProps = {
  data: NodeObjectWithMetadata;
  schema: ModelSchema;
  permission: Permission;
};

const GraphqlQueryDetailsCard = ({ data, schema, permission }: GraphqlQueryDetailsCardProps) => {
  return (
    <Card className="overflow-x-hidden p-0">
      <GraphqlQueryDetailsTitle data={data} schema={schema} permission={permission} />

      <GraphqlQueryPropertyList data={data} schema={schema} permission={permission} />
    </Card>
  );
};

const GraphqlQueryDetailsTitle = ({ data, schema, permission }: GraphqlQueryDetailsCardProps) => {
  return (
    <>
      <CardWithBorder.Title className="flex items-center gap-1 rounded-t">
        <Badge variant="blue">{schema.namespace}</Badge>

        <span>
          {schema.name} - {getNodeLabel(data)}
        </span>

        <ObjectEditSlideOverTrigger
          data={data}
          schema={schema}
          onUpdateComplete={() => queryClient.invalidateQueries({ queryKey: objectQueryKeys.all })}
          permission={permission}
        />
      </CardWithBorder.Title>
    </>
  );
};

const GraphqlQueryPropertyList = ({ data, schema, permission }: GraphqlQueryDetailsCardProps) => {
  // Filter out "query" attribute since it's displayed in GraphqlQueryViewerCard
  const schemaWithoutQuery: ModelSchema = {
    ...schema,
    attributes: schema.attributes?.filter((attr) => attr.name !== "query"),
  };

  return (
    <ObjectDataDisplay
      objectSchema={schemaWithoutQuery}
      objectData={data}
      permission={permission}
    />
  );
};

export default GraphqlQueryDetailsCard;
