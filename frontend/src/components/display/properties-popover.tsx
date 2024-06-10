import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import { usePermission } from "@/hooks/usePermission";
import ObjectItemMetaEdit from "@/screens/object-item-meta-edit/object-item-meta-edit";
import { Icon } from "@iconify-icon/react";
import { useAtom, useAtomValue } from "jotai/index";
import { useState } from "react";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { metaEditFieldDetailsState } from "../../state/atoms/showMetaEdit.atom copy";
import { ButtonWithTooltip } from "../buttons/button-primitive";
import MetaDetailsTooltip from "./meta-details-tooltips";
import SlideOver from "./slide-over";

interface PropertiesEditTriggerProps {
  type: "attribute" | "relationship";
  properties: any;
  attributeSchema: any;
  refetch?: () => Promise<unknown>;
  data: any;
  schema: any;
  hideHeader?: boolean;
}

const PropertiesPopover = ({
  type,
  properties,
  attributeSchema,
  refetch,
  data,
  schema,
  hideHeader,
}: PropertiesEditTriggerProps) => {
  const permission = usePermission();
  const branch = useAtomValue(currentBranchAtom);
  const [showMetaEditModal, setShowMetaEditModal] = useState(false);
  const [metaEditFieldDetails, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);

  return (
    <>
      <MetaDetailsTooltip
        updatedAt={properties.updated_at}
        source={properties.source}
        owner={properties.owner}
        isFromProfile={properties.is_from_profile}
        isProtected={properties.is_protected}
        header={
          !hideHeader &&
          !attributeSchema.read_only && (
            <div className="flex justify-between items-center pl-2 p-1 pt-0 border-b">
              <div className="font-semibold">{attributeSchema.label}</div>

              <ButtonWithTooltip
                variant="ghost"
                size="icon"
                onClick={() => {
                  setMetaEditFieldDetails({
                    type,
                    attributeOrRelationshipName: attributeSchema.name,
                    label: attributeSchema.label || attributeSchema.name,
                  });
                  setShowMetaEditModal(true);
                }}
                disabled={!permission.write.allow}
                tooltipEnabled={!permission.write.allow}
                tooltipContent={permission.write.message ?? undefined}
                data-testid="properties-edit-button">
                <Icon icon="mdi:pencil" className="text-custom-blue-500" />
              </ButtonWithTooltip>
            </div>
          )
        }
      />

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex items-center w-full">
              <span className="text-lg font-semibold mr-3">{metaEditFieldDetails?.label}</span>
              <div className="flex-1"></div>
              <div className="flex items-center">
                <Icon icon="mdi:layers-triple" />
                <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
              </div>
            </div>
            <div className="text-gray-500">Metadata</div>
          </div>
        }
        open={showMetaEditModal}
        setOpen={setShowMetaEditModal}>
        <ObjectItemMetaEdit
          closeDrawer={() => setShowMetaEditModal(false)}
          onUpdateComplete={() => refetch && refetch()}
          attributeOrRelationshipToEdit={
            (data as any)[metaEditFieldDetails?.attributeOrRelationshipName]?.properties ||
            (data as any)[metaEditFieldDetails?.attributeOrRelationshipName]
          }
          schema={schema}
          attributeOrRelationshipName={metaEditFieldDetails?.attributeOrRelationshipName}
          type={metaEditFieldDetails?.type!}
          row={data}
        />
      </SlideOver>
    </>
  );
};

export default PropertiesPopover;
