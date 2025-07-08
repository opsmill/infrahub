import { NodeSchema } from "@/entities/schema/types";
import { TableColumnHeader } from "./table-column-header";

interface ProposedChangesTableHeaderProps {
  schema: NodeSchema;
}

export function ProposedChangesTableHeader({ schema }: ProposedChangesTableHeaderProps) {
  const stateAttribute = schema.attributes.find((attribute) => {
    return attribute.name === "state";
  });

  const sourceBranchAttribute = schema.attributes.find((attribute) => {
    return attribute.name === "source_branch";
  });

  const destinationBranchAttribute = schema.attributes.find((attribute) => {
    return attribute.name === "destination_branch";
  });

  const authorRelationship = schema.relationships.find((relationship) => {
    return relationship.name === "created_by";
  });

  const reviewersRelationship = schema.relationships.find((relationship) => {
    return relationship.name === "reviewers";
  });

  const approversRelationship = schema.relationships.find((relationship) => {
    return relationship.name === "approved_by";
  });

  return (
    <div className="flex items-center justify-between gap-2 p-3 pt-0">
      <div className="flex items-center">
        <span>Closed</span>
        <span>Opened</span>
        <span>Draft</span>
      </div>

      <div className="flex items-center">
        <TableColumnHeader schema={schema} columnSchema={stateAttribute} />
        <TableColumnHeader schema={schema} columnSchema={sourceBranchAttribute} />
        <TableColumnHeader schema={schema} columnSchema={destinationBranchAttribute} />
        <TableColumnHeader schema={schema} columnSchema={authorRelationship} />
        <TableColumnHeader schema={schema} columnSchema={reviewersRelationship} />
        <TableColumnHeader schema={schema} columnSchema={approversRelationship} />
      </div>
    </div>
  );
}
