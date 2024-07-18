import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { usePermission } from "@/hooks/usePermission";
import { useState } from "react";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
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
          <SlideOverTitle
            schema={schema}
            currentObjectLabel={objectDetailsData?.display_label}
            title="Select group(s)"
            subtitle="Select one or more groups to assign"
          />
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
