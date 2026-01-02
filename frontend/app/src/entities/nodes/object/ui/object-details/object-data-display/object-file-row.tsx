import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { queryClient } from "@/shared/api/rest/client";
import { Button } from "@/shared/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ObjectForm from "@/shared/components/form/object-form";

import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { FileCard } from "@/entities/nodes/object/ui/object-details/object-data-display/file-card";
import { ObjectDataRow } from "@/entities/nodes/object/ui/object-details/object-data-display/object-data-row";
import type {
  FileNodeData,
  FileRelationshipData,
  FileRelationshipManyData,
  FileRelationshipOneData,
} from "@/entities/nodes/object/ui/object-details/object-data-display/types/file-types";
import ObjectItemEditComponent from "@/entities/nodes/object-item-edit/object-item-edit-paginated";
import type { Permission } from "@/entities/permission/types";
import type { RelationshipSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface ObjectFileRowProps {
  relationshipSchema: RelationshipSchema;
  relationshipData: FileRelationshipData;
  permission: Permission;
}

export function ObjectFileRow({
  relationshipSchema,
  relationshipData,
  permission,
}: ObjectFileRowProps) {
  const relationshipLabel = relationshipSchema.label ?? relationshipSchema.name;

  if (relationshipSchema.cardinality === "one") {
    return (
      <FileOneRow
        relationshipSchema={relationshipSchema}
        relationshipData={relationshipData as FileRelationshipOneData}
        relationshipLabel={relationshipLabel}
        permission={permission}
      />
    );
  }

  return (
    <FileManyRow
      relationshipSchema={relationshipSchema}
      relationshipData={relationshipData as FileRelationshipManyData}
      relationshipLabel={relationshipLabel}
      permission={permission}
    />
  );
}

interface FileOneRowProps {
  relationshipSchema: RelationshipSchema;
  relationshipData: FileRelationshipOneData;
  relationshipLabel: string;
  permission: Permission;
}

function FileOneRow({
  relationshipSchema,
  relationshipData,
  relationshipLabel,
  permission,
}: FileOneRowProps) {
  const [showEditForm, setShowEditForm] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const { schema: peerSchema } = useSchema(relationshipSchema.peer);

  const fileNode = relationshipData.node;
  const canEdit = permission.update.isAllowed;

  return (
    <ObjectDataRow
      name={relationshipLabel}
      value={
        fileNode ? (
          <>
            <FileCard file={relationshipData} onClick={() => canEdit && setShowEditForm(true)} />

            {showEditForm && peerSchema && (
              <SlideOver
                title={
                  <SlideOverTitle
                    schema={peerSchema}
                    currentObjectLabel={fileNode.display_label ?? fileNode.name?.value}
                    title={`Edit ${fileNode.display_label ?? fileNode.name?.value}`}
                  />
                }
                open={true}
                setOpen={() => setShowEditForm(false)}
              >
                <ObjectItemEditComponent
                  closeDrawer={() => setShowEditForm(false)}
                  onUpdateComplete={async () => {
                    await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
                    setShowEditForm(false);
                  }}
                  objectId={fileNode.id}
                  objectname={fileNode.__typename}
                />
              </SlideOver>
            )}
          </>
        ) : (
          <>
            <Button
              variant="outline"
              size="sm"
              className="w-fit"
              disabled={!canEdit}
              onClick={() => setShowAddForm(true)}
              data-testid="add-file-button"
            >
              <Icon icon="mdi:plus" className="mr-1" />
              Add file
            </Button>

            {showAddForm && peerSchema && (
              <SlideOver
                title={
                  <SlideOverTitle schema={peerSchema} currentObjectLabel={undefined} title="Add File" />
                }
                open={true}
                setOpen={() => setShowAddForm(false)}
              >
                <ObjectForm
                  kind={peerSchema.kind as string}
                  onSuccess={async () => {
                    await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
                    setShowAddForm(false);
                  }}
                  onCancel={() => setShowAddForm(false)}
                />
              </SlideOver>
            )}
          </>
        )
      }
    />
  );
}

interface FileManyRowProps {
  relationshipSchema: RelationshipSchema;
  relationshipData: FileRelationshipManyData;
  relationshipLabel: string;
  permission: Permission;
}

function FileManyRow({
  relationshipSchema,
  relationshipData,
  relationshipLabel,
  permission,
}: FileManyRowProps) {
  const [editingFile, setEditingFile] = useState<FileNodeData | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const { schema: peerSchema } = useSchema(relationshipSchema.peer);

  const fileEdges = relationshipData.edges;
  const hasFiles = fileEdges.length > 0;

  return (
    <ObjectDataRow
      name={relationshipLabel}
      value={
        <div className="flex flex-col gap-2">
          {hasFiles ? (
            fileEdges.map((edge) => {
              const fileNode = edge.node;
              if (!fileNode) return null;

              return (
                <FileCard key={fileNode.id} file={edge} onClick={() => setEditingFile(fileNode)} />
              );
            })
          ) : (
            <span className="text-gray-500">-</span>
          )}

          {/* Add file button - always shown for cardinality many */}
          <Button
            variant="outline"
            size="sm"
            className="w-fit"
            disabled={!permission.update.isAllowed}
            onClick={() => setShowAddForm(true)}
            data-testid="add-file-button"
          >
            <Icon icon="mdi:plus" className="mr-1" />
            Add file
          </Button>

          {/* Add file slide-over */}
          {showAddForm && peerSchema && (
            <SlideOver
              title={
                <SlideOverTitle schema={peerSchema} currentObjectLabel={undefined} title="Add File" />
              }
              open={true}
              setOpen={() => setShowAddForm(false)}
            >
              <ObjectForm
                kind={peerSchema.kind as string}
                onSuccess={async () => {
                  await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
                  setShowAddForm(false);
                }}
                onCancel={() => setShowAddForm(false)}
              />
            </SlideOver>
          )}

          {/* Edit file slide-over */}
          {editingFile && peerSchema && (
            <SlideOver
              title={
                <SlideOverTitle
                  schema={peerSchema}
                  currentObjectLabel={editingFile.display_label ?? editingFile.name?.value}
                  title={`Edit ${editingFile.display_label ?? editingFile.name?.value}`}
                />
              }
              open={true}
              setOpen={() => setEditingFile(null)}
            >
              <ObjectItemEditComponent
                closeDrawer={() => setEditingFile(null)}
                onUpdateComplete={async () => {
                  await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
                  setEditingFile(null);
                }}
                objectId={editingFile.id}
                objectname={editingFile.__typename}
              />
            </SlideOver>
          )}
        </div>
      }
    />
  );
}
