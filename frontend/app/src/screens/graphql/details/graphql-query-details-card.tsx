import { CopyToClipboard } from "@/components/buttons/copy-to-clipboard";
import PropertiesPopover from "@/components/display/properties-popover";
import ObjectEditSlideOverTrigger from "@/components/form/object-edit-slide-over-trigger";
import { Property, PropertyList } from "@/components/table/property-list";
import { Badge } from "@/components/ui/badge";
import { CardWithBorder } from "@/components/ui/card";
import { Link } from "@/components/ui/link";
import { Tooltip } from "@/components/ui/tooltip";
import { RELATIONSHIP_VIEW_BLACKLIST } from "@/config/constants";
import { CoreGraphQlQuery } from "@/generated/graphql";
import { iNodeSchema } from "@/state/atoms/schema.atom";
import { constructPath } from "@/utils/fetch";
import { AttributeType, ObjectAttributeValue } from "@/utils/getObjectItemDisplayValue";
import { getObjectDetailsUrl, getObjectDetailsUrl2 } from "@/utils/objects";
import { Permission } from "@/utils/permissions";
import { Icon } from "@iconify-icon/react";

type GraphqlQueryDetailsCardProps = {
  data: CoreGraphQlQuery;
  schema: iNodeSchema;
  refetch: () => Promise<unknown>;
  permission: Permission;
};

const GraphqlQueryDetailsCard = ({
  data,
  schema,
  refetch,
  permission,
}: GraphqlQueryDetailsCardProps) => {
  return (
    <CardWithBorder>
      <GraphqlQueryDetailsTitle
        data={data}
        schema={schema}
        refetch={refetch}
        permission={permission}
      />

      <GraphqlQueryPropertyList
        data={data}
        schema={schema}
        refetch={refetch}
        permission={permission}
      />
    </CardWithBorder>
  );
};

const GraphqlQueryDetailsTitle = ({
  data,
  schema,
  refetch,
  permission,
}: GraphqlQueryDetailsCardProps) => {
  return (
    <>
      <CardWithBorder.Title className="flex items-center gap-1">
        <Badge variant="blue">{schema.namespace}</Badge>

        <span>
          {schema.name} - {data.display_label}
        </span>

        <ObjectEditSlideOverTrigger
          data={data}
          schema={schema}
          onUpdateComplete={refetch}
          permission={permission}
        />
      </CardWithBorder.Title>
    </>
  );
};

const GraphqlQueryPropertyList = ({
  data,
  schema,
  refetch,
  permission,
}: GraphqlQueryDetailsCardProps) => {
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
              attributeValue={graphqlQueryAttribute}
            />

            <div className="flex items-center">
              {graphqlQueryAttribute.is_protected && <ProtectedIcon />}

              <PropertiesPopover
                type="attribute"
                attributeSchema={attributeSchema}
                properties={graphqlQueryAttribute}
                refetch={refetch}
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
                <Link to={constructPath(getObjectDetailsUrl(node.id, node.__typename))}>
                  {node?.display_label}
                </Link>

                {properties.is_protected && <ProtectedIcon />}

                <PropertiesPopover
                  type="relationship"
                  hideHeader
                  attributeSchema={relationshipSchema}
                  properties={properties}
                  refetch={refetch}
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
              <Link to={getObjectDetailsUrl2(relationshipData.__typename, relationshipData.id)}>
                {relationshipData?.display_label}
              </Link>

              <div className="flex items-center">
                {relationshipProperties.is_protected && <ProtectedIcon />}

                <PropertiesPopover
                  type="relationship"
                  attributeSchema={relationshipSchema}
                  properties={relationshipProperties}
                  refetch={refetch}
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
