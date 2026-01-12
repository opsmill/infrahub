import React from "react";
import { Link, type LinkProps } from "react-router";

import { Row, type RowProps } from "@/shared/components/container";
import { classNames, sortByOrderWeight } from "@/shared/utils/common";

import { getPrefixAttributesVisibleInListView } from "@/entities/ipam/ip-prefixes/utils/get-prefix-attributes-visible-in-list-view";
import { NodeMetadataPopover } from "@/entities/nodes/object/ui/object-details/node-metadata-popover";
import { ObjectDetailsMenu } from "@/entities/nodes/object/ui/object-details/object-details-menu";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import { DetailsButtons } from "@/entities/nodes/object-item-details/action-buttons/details-buttons";
import type {
  NodeAttribute,
  NodeCore,
  NodeObject,
  NodeRelationshipMany,
  NodeRelationshipOne,
} from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { Permission } from "@/entities/permission/types";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";

interface IpPrefixDetailsHeaderProps extends RowProps {
  ipPrefixSchema: ModelSchema;
  ipPrefixNode: NodeObject;
  permission: Permission;
}

export function IpamDetailsHeader({
  ipPrefixNode,
  ipPrefixSchema,
  permission,
  className,
  ...props
}: IpPrefixDetailsHeaderProps) {
  const attributesVisible = getPrefixAttributesVisibleInListView(
    ipPrefixSchema.attributes ?? []
  ).filter((rel) => rel.name !== "address");
  const relationshipsVisible = getRelationshipsVisibleInListView(
    ipPrefixSchema.relationships ?? []
  ).filter((rel) => rel.name !== "parent");

  const orderedFields: Array<AttributeSchema | RelationshipSchema> = sortByOrderWeight([
    ...attributesVisible,
    ...relationshipsVisible,
  ]);

  return (
    <Row className={classNames("relative", className)} {...props}>
      <h2 className="whitespace-nowrap font-semibold text-lg">{getNodeLabel(ipPrefixNode)}</h2>

      <NodeMetadataPopover objectId={ipPrefixNode.id} objectKind={ipPrefixNode.__typename} />

      <Row className="relative grow gap-2.5 overflow-hidden">
        <Fade />
        {orderedFields.map((field, index) => {
          let displayValue: React.ReactNode = "-";

          if ("peer" in field) {
            if (field.cardinality === "many") {
              const relData = ipPrefixNode[field.name] as NodeRelationshipMany | undefined;
              if (relData && relData.edges?.length > 0) {
                displayValue = relData.edges.map(({ node }, index) =>
                  node ? (
                    <>
                      {index > 0 && ", "}
                      <RelationshipDisplay key={node.id} node={node} />
                    </>
                  ) : null
                );
              }
            } else {
              const relData = ipPrefixNode[field.name] as NodeRelationshipOne | undefined;
              displayValue = relData?.node ? <RelationshipDisplay node={relData.node} /> : "-";
            }
          } else {
            const attributeData = ipPrefixNode[field.name] as NodeAttribute | undefined;
            const attributeValue = attributeData?.value?.toString();
            displayValue =
              attributeValue && field.name === "utilization"
                ? `${attributeValue}%`
                : (attributeValue ?? "-");
          }

          return (
            <React.Fragment key={field.name}>
              {index > 0 && <Divider />}
              <Group>
                <Title>{field.label}</Title>
                <Value>{displayValue}</Value>
              </Group>
            </React.Fragment>
          );
        })}
      </Row>

      <DetailsButtons
        schema={ipPrefixSchema}
        objectDetailsData={ipPrefixNode}
        permission={permission}
        className="ml-auto"
      />

      <ObjectDetailsMenu
        objectSchema={ipPrefixSchema}
        objectData={ipPrefixNode}
        permission={permission}
      />
    </Row>
  );
}

const Divider = () => <div className="h-5 w-px shrink-0 bg-gray-200" />;

const Group = ({ className, children, ...props }: React.HTMLProps<HTMLDivElement>) => (
  <div className={classNames("not-last:max-w-50 text-xs", className)} {...props}>
    {children}
  </div>
);

const Title = ({ className, children, ...props }: React.HTMLProps<HTMLDivElement>) => (
  <div className={classNames("truncate text-custom-blue-800", className)} {...props}>
    {children}
  </div>
);

const Value = ({ className, children, ...props }: React.HTMLProps<HTMLDivElement>) => (
  <div className={classNames("truncate font-medium text-gray-600", className)} {...props}>
    {children}
  </div>
);

const Fade = ({ className, ...props }: React.HTMLProps<HTMLDivElement>) => (
  <div
    className={classNames(
      "pointer-events-none absolute top-0 right-0 bottom-0 w-40 bg-gradient-to-r from-transparent via-white/70 to-white",
      className
    )}
    {...props}
  />
);

interface RelationshipDisplayProps extends Omit<LinkProps, "to"> {
  node: NodeCore;
}

const RelationshipDisplay = ({ className, node, ...props }: RelationshipDisplayProps) => (
  <Link
    to={getObjectDetailsUrl(node.__typename, node.id)}
    className={classNames("inline-flex underline decoration-dotted", className)}
    {...props}
  >
    {getNodeLabel(node)}
  </Link>
);
