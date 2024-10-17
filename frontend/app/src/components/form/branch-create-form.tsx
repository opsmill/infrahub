import { Button } from "@/components/buttons/button-primitive";
import CheckboxField from "@/components/form/fields/checkbox.field";
import InputField from "@/components/form/fields/input.field";
import { isMinLength, isRequired } from "@/components/form/utils/validation";
import { Form, FormSubmit } from "@/components/ui/form";
import { QSP } from "@/config/qsp";
import { Branch } from "@/generated/graphql";
import { BRANCH_CREATE } from "@/graphql/mutations/branches/createBranch";
import { useMutation } from "@/hooks/useQuery";
import { branchesState } from "@/state/atoms/branches.atom";
import { useAtom } from "jotai";
import { StringParam, useQueryParam } from "use-query-params";

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
    <Form
      className="p-2 space-y-4"
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

        <FormSubmit>Create a new branch</FormSubmit>
      </div>
    </Form>
  );
};

export default BranchCreateForm;
