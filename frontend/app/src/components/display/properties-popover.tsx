import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import ObjectItemMetaEdit from "@/screens/object-item-meta-edit/object-item-meta-edit";
import { metaEditFieldDetailsState } from "@/state/atoms/showMetaEdit.atom copy";
import { Permission } from "@/utils/permissions";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai/index";
import { useState } from "react";
import MetaDetailsTooltip from "./meta-details-tooltips";
import SlideOver, { SlideOverTitle } from "./slide-over";

interface PropertiesEditTriggerProps {
  type: "attribute" | "relationship";
  properties: any;
  attributeSchema: any;
  refetch?: () => Promise<unknown>;
  data: any;
  schema: any;
  hideHeader?: boolean;
  permission: Permission;
}

const PropertiesPopover = ({
  type,
  properties,
  attributeSchema,
  refetch,
  data,
  schema,
  hideHeader,
  permission,
}: PropertiesEditTriggerProps) => {
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
                disabled={!permission.create.isAllowed}
                tooltipEnabled={!permission.create.isAllowed}
                tooltipContent={permission.create.message ?? undefined}
                data-testid="properties-edit-button"
              >
                <Icon icon="mdi:pencil" className="text-custom-blue-500" />
              </ButtonWithTooltip>
            </div>
          )
        }
      />

      <SlideOver
        title={
          <SlideOverTitle
            schema={schema}
            currentObjectLabel={data?.display_label}
            title={`${metaEditFieldDetails?.label} properties`}
            subtitle={`Update the properties of ${metaEditFieldDetails?.label}`}
          />
        }
        open={showMetaEditModal}
        setOpen={setShowMetaEditModal}
      >
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
