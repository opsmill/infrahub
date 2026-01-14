import { Icon } from "@iconify-icon/react";

import type { CoreGraphQlQuery } from "@/shared/api/graphql/generated/graphql";
import { queryClient } from "@/shared/api/rest/client";
import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import PropertiesPopover from "@/shared/components/display/properties-popover";
import ObjectEditSlideOverTrigger from "@/shared/components/form/object-edit-slide-over-trigger";
import { type Property, PropertyList } from "@/shared/components/table/property-list";
import { Badge } from "@/shared/components/ui/badge";
import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { Link } from "@/shared/components/ui/link";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { RELATIONSHIP_VIEW_BLACKLIST } from "@/shared/config/constants";

import {
  type AttributeType,
  ObjectAttributeValue,
} from "@/entities/nodes/getObjectItemDisplayValue";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

type GraphqlQueryDetailsCardProps = {
  data: CoreGraphQlQuery;
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
  const properties: Property[] = [
    {
      name: "ID",
      value: (
        <div className="inline-flex items-center gap-1">
          {data.id} <CopyToClipboard className="text-gray-500" text={data.id} />
        </div>
      ),
    },
    ...(schema.attributes ?? []).map((attributeSchema) => {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars,no-unused-vars
      const { __typename, ...aaa } = data;
      const graphqlQueryAttribute = (aaa as Record<string, AttributeType | undefined>)[
        attributeSchema.name
      ];

      if (!graphqlQueryAttribute) {
        return {
          name: attributeSchema.label || attributeSchema.name,
          value: "-",
        };
      }

      return {
        name: attributeSchema.label || attributeSchema.name,
        value: (
          <div className="flex items-center justify-between">
            <ObjectAttributeValue
              attributeSchema={attributeSchema}
              attributeData={graphqlQueryAttribute}
            />

            <div className="flex items-center">
              {graphqlQueryAttribute.is_protected && <ProtectedIcon />}

              <PropertiesPopover
                type="attribute"
                attributeSchema={attributeSchema}
                properties={graphqlQueryAttribute}
                data={data}
                schema={schema}
                permission={permission}
              />
            </div>
          </div>
        ),
      };
    }),
    ...(schema.relationships ?? [])
      .filter(({ name }) => !RELATIONSHIP_VIEW_BLACKLIST.includes(name))
      .map((relationshipSchema) => {
        if (relationshipSchema.cardinality === "many") {
          const relationshipData = (data as any)[relationshipSchema.name]?.edges;

          return {
            name: relationshipSchema.label || relationshipSchema.name,
            value: relationshipData?.map(({ node, properties }: any) => (
              <div key={node.id} className="flex items-center justify-between">
                <Link to={getObjectDetailsUrl(node.__typename, node.id)}>
                  {node ? getNodeLabel(node) : ""}
                </Link>

                {properties.is_protected && <ProtectedIcon />}

                <PropertiesPopover
                  type="relationship"
                  hideHeader
                  attributeSchema={relationshipSchema}
                  properties={properties}
                  data={data}
                  schema={schema}
                  permission={permission}
                />
              </div>
            )),
          };
        }

        const { node: relationshipData, properties: relationshipProperties } = (data as any)[
          relationshipSchema.name
        ];

        return {
          name: relationshipSchema.label || relationshipSchema.name,
          value: relationshipData && (
            <div className="flex items-center justify-between">
              <Link to={getObjectDetailsUrl(relationshipData.__typename, relationshipData.id)}>
                {relationshipData ? getNodeLabel(relationshipData) : ""}
              </Link>

              <div className="flex items-center">
                {relationshipProperties.is_protected && <ProtectedIcon />}

                <PropertiesPopover
                  type="relationship"
                  attributeSchema={relationshipSchema}
                  properties={relationshipProperties}
                  data={data}
                  schema={schema}
                  permission={permission}
                />
              </div>
            </div>
          ),
        };
      }),
  ].filter(({ name }) => name !== "Query");

  return <PropertyList properties={properties} />;
};

const ProtectedIcon = () => (
  <Tooltip content="protected" enabled>
    <Icon icon="mdi:lock-outline" className="text-gray-500" />
  </Tooltip>
);

export default GraphqlQueryDetailsCard;
