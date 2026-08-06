import { Button } from "@infrahub/ui";

import type { Branch } from "@/shared/api/graphql/generated/types";
import { Row } from "@/shared/components/container";
import CheckboxField from "@/shared/components/form/fields/checkbox.field";
import InputField from "@/shared/components/form/fields/input.field";
import { isMinLength, isRequired } from "@/shared/components/form/utils/validation";
import { Form, FormSubmit } from "@/shared/components/ui/form";

import { SYNC_WITH_GIT_DESCRIPTION } from "@/entities/branches/domain/model/branch";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
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
  const { setCurrentBranch } = useCurrentBranch();
  const { mutateAsync: createBranch } = useCreateBranchMutation();

  const handleSubmit = async (branchFormData: BranchFormData) => {
    await createBranch(branchFormData, {
      onSuccess: async (branchCreated) => {
        if (!branchCreated) return;
        setCurrentBranch(branchCreated);
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

      <CheckboxField
        name="sync_with_git"
        label="Sync with Git"
        description={SYNC_WITH_GIT_DESCRIPTION}
      />

      <Row className="justify-end">
        <Button variant="outline" size="sm" onPress={onCancel}>
          Cancel
        </Button>

        <FormSubmit size="sm" data-testid="submit-create-new-branch">
          Create a new branch
        </FormSubmit>
      </Row>
    </Form>
  );
};

export default BranchCreateForm;
