import { ChevronsUpDownIcon } from "lucide-react";
import { Pressable } from "react-aria-components";
import { Link } from "react-router";

import { Breadcrumb } from "@/shared/components/aria/breadcrumbs";
import { MenuTrigger } from "@/shared/components/aria/menu";
import { Popover } from "@/shared/components/aria/popover";
import { Button } from "@/shared/components/buttons/button-primitive";
import { Col, Row } from "@/shared/components/container";

import { ObjectAutocomplete } from "@/entities/nodes/object/ui/object-autocomplete";
import { ObjectRelationshipList } from "@/entities/nodes/object/ui/object-relationship-list";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { GetRelationshipsParams } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships";
import type { NodeCore } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { RelationshipSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function BreadcrumbItemObject({
  node,
  autocompleteObjectKind,
  parentRelationshipSchema,
  parentId,
  filterQuery,
}: {
  node: NodeCore;
  autocompleteObjectKind?: string;
  parentId?: string;
  parentRelationshipSchema?: RelationshipSchema;
  filterQuery?: GetRelationshipsParams["filterQuery"];
}) {
  const { schema } = useSchema(node.__typename);

  const { schema: parentSchema } = useSchema(parentRelationshipSchema?.peer);
  const parentToChildRelationshipSchema = parentRelationshipSchema
    ? parentSchema?.relationships?.find((rel) => {
        if (rel.identifier !== parentRelationshipSchema.identifier) return false;

        switch (rel.direction) {
          case "bidirectional":
            return parentRelationshipSchema.direction === "bidirectional";
          case "inbound":
            return parentRelationshipSchema.direction === "outbound";
          case "outbound":
            return parentRelationshipSchema.direction === "inbound";
          default:
            return false;
        }
      })
    : null;
  const { schema: parentToChildSchema, isGeneric: isGenericParentToChild } = useSchema(
    parentToChildRelationshipSchema?.peer
  ); // TO FIX: https://github.com/opsmill/infrahub/issues/7748, generic on hierarchy do not have parent__ids filter

  return (
    <Breadcrumb>
      <Row className="items-end gap-0.5 pr-1 pl-2">
        <Col className="gap-0 py-0.5">
          <Link
            to={getObjectDetailsUrl(node.__typename)}
            className="truncate text-neutral-600 text-xs leading-3.5 hover:underline"
          >
            {schema?.label}
          </Link>

          <Link
            to={getObjectDetailsUrl(node.__typename, node.id)}
            className="truncate font-medium text-sm leading-4 hover:underline"
          >
            {getNodeLabel(node)}
          </Link>
        </Col>

        <MenuTrigger>
          <Pressable>
            <Button
              variant="ghost"
              className="size-5 p-0"
              aria-label={`Select a different ${schema?.label ?? "object"}`}
            >
              <ChevronsUpDownIcon className="size-3.5" />
            </Button>
          </Pressable>

          <Popover className="bg-stone-100/50 backdrop-blur">
            {parentRelationshipSchema &&
            parentId &&
            parentToChildRelationshipSchema?.kind === "Hierarchy" &&
            isGenericParentToChild &&
            !parentToChildSchema.hierarchical ? (
              <ObjectRelationshipList
                className="max-h-58"
                parentKind={parentRelationshipSchema.peer}
                parentId={parentId}
                relationshipName={parentToChildRelationshipSchema.name}
                relationshipSchema={parentToChildSchema}
              />
            ) : (
              <ObjectAutocomplete
                className="max-h-58"
                {...(parentRelationshipSchema && parentToChildRelationshipSchema && parentId
                  ? {
                      objectKind: parentToChildRelationshipSchema.peer,
                      filterQuery: {
                        [`${parentRelationshipSchema.name}__ids`]: [parentId],
                        ...filterQuery,
                      },
                    }
                  : {
                      objectKind: autocompleteObjectKind ?? node.__typename,
                      filterQuery,
                    })}
              />
            )}
          </Popover>
        </MenuTrigger>
      </Row>
    </Breadcrumb>
  );
}
