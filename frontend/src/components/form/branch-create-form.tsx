import React from "react";
import { useAtom } from "jotai";
import { useMutation } from "@apollo/client";
import { StringParam, useQueryParam } from "use-query-params";
import DynamicForm from "./dynamic-form";
import { BRANCH_CREATE } from "../../graphql/mutations/branches/createBranch";
import { Branch } from "../../generated/graphql";
import { branchesState } from "../../state/atoms/branches.atom";
import { QSP } from "../../config/qsp";

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
        await handleSubmit(data as BranchFormData);
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
          defaultValue: false,
        },
      ]}
    />
  );
};

export default BranchCreateForm;
