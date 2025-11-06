import { ChevronsUpDownIcon } from "lucide-react";
import { Link } from "react-router";

import { Button } from "@/shared/components/aria/button";
import { MenuTrigger } from "@/shared/components/aria/menu";
import { Popover } from "@/shared/components/aria/popover";
import { Col, Row } from "@/shared/components/container";
import { BreadcrumbSeparator } from "@/shared/components/ui/breadcrumb";

import { ObjectAutocomplete } from "@/entities/nodes/object/ui/object-autocomplete";
import type { NodeCore } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { RelationshipSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function BreadcrumbItemObject({
  node,
  autocompleteObjectKind,
  parentRelationshipSchema,
  parentId,
}: {
  node: NodeCore;
  autocompleteObjectKind?: string;
  parentId?: string;
  parentRelationshipSchema?: RelationshipSchema;
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

  return (
    <>
      <BreadcrumbSeparator />
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
            {node.display_label}
          </Link>
        </Col>

        <MenuTrigger>
          <Button variant="ghost" className="size-5 p-0">
            <ChevronsUpDownIcon className="size-3.5" />
          </Button>

          <Popover className="bg-stone-100/50 backdrop-blur">
            <ObjectAutocomplete
              className="max-h-58"
              {...(parentRelationshipSchema && parentToChildRelationshipSchema && parentId
                ? {
                    objectKind: parentToChildRelationshipSchema.peer,
                    filters: {
                      [`${parentRelationshipSchema.name}__ids`]: [parentId],
                    },
                  }
                : { objectKind: autocompleteObjectKind ?? node.__typename })}
            />
          </Popover>
        </MenuTrigger>
      </Row>
    </>
  );
}
