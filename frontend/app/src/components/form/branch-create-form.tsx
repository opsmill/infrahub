import { QSP } from "@/config/qsp";
import { Branch } from "@/generated/graphql";
import { BRANCH_CREATE } from "@/graphql/mutations/branches/createBranch";
import { branchesState } from "@/state/atoms/branches.atom";
import { useMutation } from "@apollo/client";
import { useAtom } from "jotai";
import { StringParam, useQueryParam } from "use-query-params";
import DynamicForm from "./dynamic-form";

type BranchFormData = {
  name: string;
  description?: string;
  sync_with_git: boolean;
};

type BranchCreateFormProps = {
  onCancel?: () => void;
  onSuccess?: (branch: Branch) => void;
};

const BranchCreateForm = ({ onCancel, onSuccess }: BranchCreateFormProps) => {
  const [branches, setBranches] = useAtom(branchesState);
  const [, setBranchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);
  const [createBranch] = useMutation(BRANCH_CREATE);

  const handleSubmit = async (branchFormData: BranchFormData) => {
    try {
      const { data } = await createBranch({
        variables: branchFormData,
      });

      const branchCreated: Branch | null = data?.BranchCreate?.object;
      if (!branchCreated) return;

      setBranches([...branches, branchCreated]);
      setBranchInQueryString(branchCreated.is_default ? undefined : branchCreated.name);

      if (onSuccess) onSuccess(branchCreated);
    } catch (error) {
      console.error("Error while creating the branch: ", error);
    }
  };

  return (
    <DynamicForm
      className="p-2"
      onCancel={onCancel}
      onSubmit={async (data) => {
        const branchData: BranchFormData = {
          name: data.name.value as string,
          description: data.description.value as string | undefined,
          sync_with_git: !!data.sync_with_git.value,
        };
        await handleSubmit(branchData);
      }}
      submitLabel="Create a new branch"
      fields={[
        {
          name: "name",
          label: "New branch name",
          type: "Text",
          rules: {
            required: true,
            minLength: { value: 3, message: "Name must be at least 3 characters long" },
          },
        },
        {
          name: "description",
          label: "New branch description",
          type: "Text",
        },
        {
          name: "sync_with_git",
          label: "Sync with Git",
          type: "Checkbox",
          defaultValue: { source: null, value: false },
        },
      ]}
    />
  );
};

export default BranchCreateForm;
