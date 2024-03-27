import { Navigate } from "react-router-dom";
import { usePermission } from "../../hooks/usePermission";
import { constructPath } from "../../utils/fetch";
import Content from "../layout/content";
import { Card } from "../../components/ui/card";
import { Select } from "../../components/inputs/select";
import { Icon } from "@iconify-icon/react";
import { ButtonWithTooltip } from "../../components/buttons/button-with-tooltip";
import { useAtomValue } from "jotai/index";
import { branchesState } from "../../state/atoms/branches.atom";
import { TextareaWithEditor } from "../../components/inputs/textarea-with-editor";
import { BUTTON_TYPES } from "../../components/buttons/button";
import { branchesToSelectOptions } from "../../utils/branches";
import { Input } from "../../components/inputs/input";

export const ProposedChangesCreate = () => {
  const permission = usePermission();
  const branches = useAtomValue(branchesState);
  const defaultBranch = branches.filter((branch) => branch.is_default);
  const sourceBranches = branches.filter((branch) => !branch.is_default);

  if (!permission.write.allow) {
    return <Navigate to={constructPath("/proposed-changes")} replace />;
  }

  return (
    <Content>
      <Content.Title title="New proposed change" />

      <div className="flex flex-col p-2 items-stretch gap-4 max-w-2xl m-auto">
        <div className="flex flex-wrap md:flex-nowrap items-center gap-2 justify-center w-full ">
          <Card className="w-full">
            <h2 className="font-semibold">Destination branch</h2>
            <p className="text-gray-600">It targets the default branch</p>
            <Select
              disabled
              value={defaultBranch[0].id}
              options={branchesToSelectOptions(defaultBranch)}
            />
          </Card>

          <Icon icon="mdi:arrow-top" className="text-xl shrink-0 md:-rotate-90" />

          <Card className="w-full">
            <h2 className="font-semibold">Source branch</h2>
            <p className="text-gray-600">Select a branch to compare</p>
            <Select options={branchesToSelectOptions(sourceBranches)} />
          </Card>
        </div>

        <div>
          <h2 className="font-semibold  mb-1">Name *</h2>
          <Input />
        </div>

        <div>
          <h2 className="font-semibold mb-1">Description</h2>
          <TextareaWithEditor
            placeholder="Add your description here..."
            className="w-full min-h-48"
          />
        </div>

        <div>
          <h2 className="font-semibold mb-1">Reviewers</h2>
          <Input />
        </div>

        <ButtonWithTooltip
          className="self-end"
          disabled={!permission.write.allow}
          buttonType={BUTTON_TYPES.MAIN}
          tooltipContent={permission.write.message ?? undefined}>
          Create proposed change
        </ButtonWithTooltip>
      </div>
    </Content>
  );
};
