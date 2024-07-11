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
        className="ml-auto"
        onClick={() => setIsAddGroupFormOpen(true)}
        disabled={!permission.write.allow}
        tooltipEnabled={!permission.write.allow}
        tooltipContent={permission.write.message ?? undefined}
        {...props}>
        + Add Groups
      </ButtonWithTooltip>

      <SlideOver
        offset={1}
        title={
          <div>
            <div className="flex justify-between">
              <div className="flex items-center gap-2 whitespace-nowrap">
                {schema.label}

                <Icon icon="mdi:chevron-right" />

                <span className="truncate">{objectDetailsData?.display_label}</span>
              </div>

              <div className="flex items-center gap-1">
                <Icon icon="mdi:layers-triple" />
                <span>{currentBranch?.name}</span>
              </div>
            </div>

            <h3 className="text-lg font-semibold flex items-center gap-2">
              Manage groups <Icon icon="mdi:chevron-right" /> Add groups
            </h3>
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
