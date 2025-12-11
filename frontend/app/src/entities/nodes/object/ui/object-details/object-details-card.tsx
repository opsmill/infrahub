import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";

import { queryClient } from "@/shared/api/rest/client";
import SlideOver from "@/shared/components/display/slide-over";
import { Card, CardWithBorder } from "@/shared/components/ui/card";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { ObjectDataDisplay } from "@/entities/nodes/object/ui/object-details/object-data-display";
import ObjectItemMetaEdit from "@/entities/nodes/object-item-meta-edit/object-item-meta-edit";
import { showMetaEditState } from "@/entities/nodes/stores/metaEditFieldDetails.atom";
import { metaEditFieldDetailsState } from "@/entities/nodes/stores/showMetaEdit.atom";
import type { NodeObjectWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { AttributeSchema, ModelSchema } from "@/entities/schema/types";

interface ObjectDetailsCardProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
  className?: string;
}

export function ObjectDetailsCard({
  objectSchema,
  objectData,
  permission,
  className,
}: ObjectDetailsCardProps) {
  const { currentBranch } = useCurrentBranch();
  const [showMetaEditModal, setShowMetaEditModal] = useAtom(showMetaEditState);
  const [metaEditFieldDetails, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);

  const handleMetadataClick = (attribute: AttributeSchema) => {
    setMetaEditFieldDetails({
      type: "attribute",
      attributeOrRelationshipName: attribute.name,
      label: attribute.label || attribute.name,
    });

    setShowMetaEditModal(true);
  };

  return (
    <>
      <Card className={className} data-testid="object-details">
        <CardWithBorder.Title className="border-gray-200 border-b">Details</CardWithBorder.Title>

        <ObjectDataDisplay
          objectSchema={objectSchema}
          objectData={objectData}
          permission={permission}
          onClickMetadata={handleMetadataClick}
        />
      </Card>

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex w-full items-center">
              <span className="mr-3 font-semibold text-lg">{metaEditFieldDetails?.label}</span>
              <div className="flex-1"></div>
              <div className="flex items-center">
                <Icon icon={"mdi:layers-triple"} />
                <div className="ml-1.5 pb-1">{currentBranch.name}</div>
              </div>
            </div>
            <div className="text-gray-500">Metadata</div>
          </div>
        }
        open={showMetaEditModal}
        setOpen={setShowMetaEditModal}
      >
        <ObjectItemMetaEdit
          closeDrawer={() => setShowMetaEditModal(false)}
          onUpdateComplete={async () => {
            await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
          }}
          attributeOrRelationshipToEdit={
            objectData[metaEditFieldDetails?.attributeOrRelationshipName]?.properties ||
            objectData[metaEditFieldDetails?.attributeOrRelationshipName]
          }
          schema={objectSchema}
          attributeOrRelationshipName={metaEditFieldDetails?.attributeOrRelationshipName}
          type={metaEditFieldDetails?.type!}
          row={objectData}
        />
      </SlideOver>
    </>
  );
}
