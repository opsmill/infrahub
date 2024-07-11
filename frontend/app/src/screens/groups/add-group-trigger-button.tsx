import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { usePermission } from "@/hooks/usePermission";
import { useAtomValue } from "jotai";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { useState } from "react";
import SlideOver from "@/components/display/slide-over";
import { Icon } from "@iconify-icon/react";
import AddGroupForm from "@/screens/groups/add-group-form";
import { iNodeSchema } from "@/state/atoms/schema.atom";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { useObjectDetails } from "@/hooks/useObjectDetails";
import { Badge } from "@/components/ui/badge";
import { ObjectHelpButton } from "@/components/menu/object-help-button";

type AddGroupTriggerButtonProps = {
  schema: iNodeSchema;
  objectId: string;
};

export default function AddGroupTriggerButton({
  schema,
  objectId,
  ...props
}: AddGroupTriggerButtonProps) {
  const permission = usePermission();
  const currentBranch = useAtomValue(currentBranchAtom);
  const [isAddGroupFormOpen, setIsAddGroupFormOpen] = useState(false);

  const { data } = useObjectDetails(schema, objectId);

  const objectDetailsData = schema && data && data[schema.kind!]?.edges[0]?.node;

  return (
    <>
      <ButtonWithTooltip
        onClick={() => setIsAddGroupFormOpen(true)}
        className="p-2"
        disabled={!permission.write.allow}
        tooltipContent={permission.write.message ?? "Add groups"}
        tooltipEnabled
        data-testid="open-group-form-button"
        {...props}>
        <Icon icon="mdi:plus" className="text-lg" />
      </ButtonWithTooltip>

      <SlideOver
        offset={1}
        title={
          <div className="space-y-2">
            <div className="flex">
              <Badge variant="blue" className="flex items-center gap-1">
                <Icon icon="mdi:layers-triple" />
                <span>{currentBranch?.name}</span>
              </Badge>

              <ObjectHelpButton
                kind={schema.kind}
                documentationUrl={schema.documentation}
                className="ml-auto"
              />
            </div>

            <div className="flex justify-between">
              <div className="text-sm flex items-center gap-2 whitespace-nowrap">
                {schema.label}

                <Icon icon="mdi:chevron-right" />

                <span className="truncate">{objectDetailsData?.display_label}</span>
              </div>
            </div>

            <div>
              <h3 className="text-lg font-semibold">Select group(s)</h3>
              <p className="text-sm">Select one or more groups to assign</p>
            </div>
          </div>
        }
        open={isAddGroupFormOpen}
        setOpen={setIsAddGroupFormOpen}>
        <AddGroupForm
          objectId={objectId}
          schema={schema}
          className="p-4"
          onCancel={() => setIsAddGroupFormOpen(false)}
          onUpdateCompleted={async () => {
            await graphqlClient.refetchQueries({ include: ["GET_GROUPS"] });
            setIsAddGroupFormOpen(false);
          }}
        />
      </SlideOver>
    </>
  );
}
