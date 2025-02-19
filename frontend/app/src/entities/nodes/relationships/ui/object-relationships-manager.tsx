import { ActiveFilterTags } from "@/entities/nodes/object/ui/filters/active-filter-tags";
import { FilterResetButton } from "@/entities/nodes/object/ui/filters/filter-reset-button";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import { RelationshipTable } from "@/entities/nodes/relationships/ui/relationship-table/relationship-table";
import { getObjectDetailsUrl2 } from "@/entities/nodes/utils";
import { useSchema } from "@/entities/schema/hooks/useSchema";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import useFilters from "@/shared/hooks/useFilters";
import { Navigate } from "react-router";
import { toast } from "react-toastify";

export interface ObjectRelationshipsManagerProps {
  parentNodeSchema: IModelSchema;
  parentNodeId: string;
  relationshipName: string;
}
export function ObjectRelationshipsManager({
  parentNodeSchema,
  parentNodeId,
  relationshipName,
}: ObjectRelationshipsManagerProps) {
  const [filters] = useFilters();
  const relationshipDefinition = parentNodeSchema.relationships?.find(
    (r) => r?.name === relationshipName
  );
  const { schema: relationshipSchema } = useSchema(relationshipDefinition?.peer);

  if (!relationshipSchema) {
    toast(
      <Alert
        type={ALERT_TYPES.ERROR}
        message={
          <>
            Relationship <strong>{relationshipName}</strong> not found in {parentNodeSchema.label}{" "}
            schema
          </>
        }
      />
    );
    return <Navigate to={getObjectDetailsUrl2(parentNodeSchema.kind as string, parentNodeId)} />;
  }

  return (
    <>
      <div className="flex items-center h-14 px-3 shrink-0">
        <FilterSearchInput schema={relationshipSchema} />

        {filters.length > 0 && (
          <>
            <ScrollArea scrollX>
              <ActiveFilterTags schema={relationshipSchema} className="mx-2" />
            </ScrollArea>
            <FilterResetButton />
          </>
        )}
      </div>

      <RelationshipTable
        parentKind={parentNodeSchema.kind as string}
        parentId={parentNodeId}
        relationshipName={relationshipName}
        relationshipSchema={relationshipSchema}
      />
    </>
  );
}
