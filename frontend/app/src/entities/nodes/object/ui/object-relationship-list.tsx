import { Icon } from "@iconify-icon/react";
import { Collection } from "react-aria-components";

import { ListBox, ListBoxItem, ListBoxLoadMoreItem } from "@/shared/components/aria/list-box";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { classNames } from "@/shared/utils/common";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import {
  type UseObjectRelationshipsParams,
  useObjectRelationships,
} from "@/entities/nodes/relationships/ui/queries/get-object-relationships.query";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";

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
      className={classNames("p-1", className)}
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
