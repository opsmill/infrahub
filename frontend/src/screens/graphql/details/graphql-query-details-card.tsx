import { CardWithBorder } from "../../../components/ui/card";
import { CoreGraphQlQuery } from "../../../generated/graphql";
import { iNodeSchema } from "../../../state/atoms/schema.atom";
import { Badge } from "../../../components/ui/badge";
import { Property, PropertyList } from "../../../components/table/property-list";
import { CopyToClipboard } from "../../../components/buttons/copy-to-clipboard";
import { AttributeType, ObjectAttributeValue } from "../../../utils/getObjectItemDisplayValue";
import { LockClosedIcon } from "@heroicons/react/24/outline";
import { constructPath } from "../../../utils/fetch";
import { getObjectDetailsUrl, getObjectDetailsUrl2 } from "../../../utils/objects";
import { RELATIONSHIP_VIEW_BLACKLIST } from "../../../config/constants";
import { Link } from "../../../components/utils/link";
import { Tooltip } from "../../../components/ui/tooltip";
import ObjectEditSlideOverTrigger from "../../../components/form/object-edit-slide-over-trigger";

type GraphqlQueryDetailsCardProps = {
  data: CoreGraphQlQuery;
  schema: iNodeSchema;
  refetch: () => Promise<unknown>;
};

const GraphqlQueryDetailsCard = ({ data, schema, refetch }: GraphqlQueryDetailsCardProps) => {
  return (
    <CardWithBorder>
      <GraphqlQueryDetailsTitle data={data} schema={schema} refetch={refetch} />

      <GraphqlQueryPropertyList data={data} schema={schema} refetch={refetch} />
    </CardWithBorder>
  );
};

const GraphqlQueryDetailsTitle = ({ data, schema, refetch }: GraphqlQueryDetailsCardProps) => {
  return (
    <>
      <CardWithBorder.Title className="flex items-center gap-1">
        <Badge variant="blue">{schema.namespace}</Badge>

        <span>
          {schema.name} - {data.display_label}
        </span>

        <ObjectEditSlideOverTrigger data={data} schema={schema} refetch={refetch} />
      </CardWithBorder.Title>
    </>
  );
};

const GraphqlQueryPropertyList = ({ data, schema, refetch }: GraphqlQueryDetailsCardProps) => {
  const properties: Property[] = [
    {
      name: "ID",
      value: (
        <div className="inline-flex items-center gap-1">
          {data.id} <CopyToClipboard text={data.id} />
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

              <FieldPropertiesPopover
                type="attribute"
                attributeSchema={attributeSchema}
                properties={graphqlQueryAttribute}
                refetch={refetch}
                data={data}
                schema={schema}
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

                <FieldPropertiesPopover
                  type="relationship"
                  attributeSchema={relationshipSchema}
                  properties={properties}
                  refetch={refetch}
                  data={data}
                  schema={schema}
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

                <FieldPropertiesPopover
                  type="relationship"
                  attributeSchema={relationshipSchema}
                  properties={relationshipProperties}
                  refetch={refetch}
                  data={data}
                  schema={schema}
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
    <LockClosedIcon className="w-4 h-4" />
  </Tooltip>
);

const FieldPropertiesPopover = () => <button>i</button>;

export default GraphqlQueryDetailsCard;
