import { useQueryState } from "nuqs";

import type { Branch } from "@/shared/api/graphql/generated/graphql";
import CheckboxField from "@/shared/components/form/fields/checkbox.field";
import InputField from "@/shared/components/form/fields/input.field";
import { isMinLength, isRequired } from "@/shared/components/form/utils/validation";
import { Button } from "@/shared/components/ui/button";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { QSP } from "@/shared/config/qsp";

import { useCreateBranchMutation } from "@/entities/branches/ui/queries/create-branch.mutation";

type BranchFormData = {
  name: string;
  description?: string;
  sync_with_git: boolean;
};

type BranchCreateFormProps = {
  onCancel?: () => void;
  onSuccess?: (branch: Branch) => void;
  defaultBranchName?: string;
};

const BranchCreateForm = ({ defaultBranchName, onCancel, onSuccess }: BranchCreateFormProps) => {
  const [, setBranchInQueryString] = useQueryState(QSP.BRANCH);
  const { mutateAsync: createBranch } = useCreateBranchMutation();

  const handleSubmit = async (branchFormData: BranchFormData) => {
    await createBranch(branchFormData, {
      onSuccess: async (branchCreated) => {
        if (!branchCreated) return;
        setBranchInQueryString(branchCreated.is_default ? null : branchCreated.name);
        if (onSuccess) onSuccess(branchCreated);
      },
      onError: (error) => {
        console.error("Error while creating the branch: ", error);
      },
    });
  };

  return (
    <Form
      className="space-y-4 p-2"
      onSubmit={async (data) => {
        const branchData: BranchFormData = {
          name: data.name.value as string,
          description: (data?.description?.value ?? undefined) as string | undefined,
          sync_with_git: !!data.sync_with_git.value,
        };
        await handleSubmit(branchData);
      }}
    >
      <InputField
        name="name"
        label="New branch name"
        defaultValue={
          defaultBranchName ? { source: { type: "user" }, value: defaultBranchName } : undefined
        }
        autoFocus
        rules={{
          required: true,
          validate: {
            required: isRequired,
            minLength: isMinLength(3),
          },
        }}
      />

      <InputField name="description" label="New branch description" />

      <CheckboxField name="sync_with_git" label="Sync with Git" rules={{ required: true }} />

      <div className="text-right">
        <Button variant="outline" className="mr-2" onClick={onCancel}>
          Cancel
        </Button>

        <FormSubmit data-testid="submit-create-new-branch">Create a new branch</FormSubmit>
      </div>
    </Form>
  );
};

export default BranchCreateForm;
