import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { usePermission } from "@/hooks/usePermission";
import { useAtomValue } from "jotai";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { useState } from "react";
import SlideOver from "@/components/display/slide-over";
import { ChevronRightIcon } from "@heroicons/react/20/solid";
import { Icon } from "@iconify-icon/react";
import AddGroupForm from "@/screens/groups/add-group-form";
import { iNodeSchema } from "@/state/atoms/schema.atom";
import graphqlClient from "@/graphql/graphqlClientApollo";

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

  const objectDetailsData = {};
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
        title={
          <div className="space-y-2">
            <div className="flex items-center w-full">
              <div className="flex items-center">
                <div className="text-base font-semibold leading-6 text-gray-900">
                  {schema.label}
                </div>
                <ChevronRightIcon
                  className="w-4 h-4 mt-1 mx-2 flex-shrink-0 text-gray-400"
                  aria-hidden="true"
                />
                <p className="mt-1 max-w-2xl text-sm text-gray-500">
                  {objectDetailsData.display_label}
                </p>
              </div>

              <div className="flex-1"></div>

              <div className="flex items-center">
                <Icon icon="mdi:layers-triple" />
                <div className="ml-1.5 pb-1">{currentBranch.name}</div>
              </div>
            </div>

            <div className="text-sm">{schema?.description}</div>

            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              {schema.kind}
            </span>
            <div className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-custom-blue-500 ring-1 ring-inset ring-custom-blue-500/10">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-custom-blue-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              ID: {objectDetailsData.id}
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
