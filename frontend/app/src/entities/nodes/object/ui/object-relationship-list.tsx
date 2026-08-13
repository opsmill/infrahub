import { ListBox, ListBoxItem, ListBoxLoadMoreItem } from "@infrahub/ui";
import { Collection } from "react-aria-components";

import { Icon } from "@/shared/components/display/icon";
import ErrorScreen from "@/shared/components/errors/error-screen";

import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import {
  type UseObjectRelationshipsParams,
  useObjectRelationships,
} from "@/entities/nodes/relationships/ui/queries/get-object-relationships.query";
import { getSchemaIcon } from "@/entities/schema/domain/rules/get-schema-icon";
import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";

interface ObjectRelationshipListProps extends UseObjectRelationshipsParams {
  className?: string;
}

export function ObjectRelationshipList({
  parentKind,
  parentId,
  relationshipName,
  relationshipSchema,
  filters,
  className,
}: ObjectRelationshipListProps) {
  const { isPending, data, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useObjectRelationships({
      parentKind,
      parentId,
      relationshipName,
      relationshipSchema,
      filters,
    });

  if (error) return <ErrorScreen message={error.message} />;

  const flatData = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <ListBox
      aria-label="object relationship list"
      className={className}
      emptyMessage="No result found"
    >
      <Collection items={flatData}>
        {(node) => {
          const { schema } = getSchema(node.__typename);
          const nodeLabel = getNodeLabel(node);

          return (
            <ListBoxItem textValue={nodeLabel} href={getObjectDetailsUrl(node.__typename, node.id)}>
              <Icon icon={getSchemaIcon(schema)} />
              <span className="truncate">{nodeLabel}</span>
            </ListBoxItem>
          );
        }}
      </Collection>

      {(isPending || hasNextPage) && (
        <ListBoxLoadMoreItem
          isLoading={isPending || isFetchingNextPage}
          onLoadMore={fetchNextPage}
        />
      )}
    </ListBox>
  );
}
