import { LinkButton } from "@/components/buttons/button-primitive";
import { MarkdownEditor } from "@/components/editor";
import { Select } from "@/components/inputs/select";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { Combobox } from "@/components/ui/combobox-legacy";
import {
  Form,
  FormField,
  FormInput,
  FormLabel,
  FormMessage,
  FormSubmit,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { ACCOUNT_GENERIC_OBJECT } from "@/config/constants";
import { CREATE_PROPOSED_CHANGE } from "@/graphql/mutations/proposed-changes/createProposedChange";
import { GET_ALL_ACCOUNTS } from "@/graphql/queries/accounts/getAllAccounts";
import { useAuth } from "@/hooks/useAuth";
import useQuery, { useMutation } from "@/hooks/useQuery";
import { branchesState } from "@/state/atoms/branches.atom";
import { branchesToSelectOptions } from "@/utils/branches";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";

export const ProposedChangeCreateForm = () => {
  const { user } = useAuth();
  const branches = useAtomValue(branchesState);
  const defaultBranch = branches.find((branch) => branch.is_default);
  const sourceBranches = branches.filter((branch) => !branch.is_default);
  const navigate = useNavigate();

  const { data: getAllAccountsData } = useQuery(GET_ALL_ACCOUNTS);

  const [createProposedChange, { error }] = useMutation(CREATE_PROPOSED_CHANGE);

  if (branches.length === 0) return <Spinner className="flex justify-center" />;

  return (
    <Form
      onSubmit={async ({ source_branch, destination_branch, name, description, reviewers }) => {
        const { data } = await createProposedChange({
          variables: {
            source_branch,
            destination_branch,
            name,
            description,
            reviewers: reviewers || [],
            created_by: {
              id: user?.id,
            },
          },
        });

        toast(<Alert type={ALERT_TYPES.SUCCESS} message="Proposed change created" />, {
          toastId: "alert-success-CoreProposedChange-created",
        });

        const url = constructPath(`/proposed-changes/${data.CoreProposedChangeCreate.object.id}`);
        navigate(url);
      }}
    >
      <Card className="flex flex-wrap md:flex-nowrap items-start gap-4 justify-center w-full shadow-sm border-gray-300">
        <FormField
          name="source_branch"
          defaultValue=""
          rules={{
            required: "Required",
            validate: {
              branchExists: (value: string) => {
                const branchesName = sourceBranches.map(({ name }) => name);
                return branchesName.includes(value) || "Branch does not exist";
              },
            },
          }}
          render={({ field }) => (
            <div className="w-full relative mb-2 flex flex-col">
              <FormLabel>Source Branch *</FormLabel>
              <FormInput>
                <Combobox
                  {...field}
                  placeholder="Select a branch..."
                  items={branchesToSelectOptions(sourceBranches).map(({ name }) => ({
                    value: name,
                    label: name,
                  }))}
                />
              </FormInput>
              <FormMessage />
            </div>
          )}
        />

        <Icon
          icon="mdi:arrow-bottom"
          className="text-xl md:mt-8 shrink-0 md:-rotate-90 text-gray-500"
        />

        <FormField
          name="destination_branch"
          defaultValue={defaultBranch?.name}
          rules={{ required: "Required" }}
          render={({ field }) => (
            <div className="w-full relative mb-2 flex flex-col">
              <FormLabel>Destination Branch *</FormLabel>
              <FormInput>
                <Combobox disabled {...field} />
              </FormInput>
              <FormMessage />
            </div>
          )}
        />
      </Card>

      <FormField
        name="name"
        defaultValue=""
        rules={{ required: "Required" }}
        render={({ field }) => {
          return (
            <div className="relative mb-2 flex flex-col">
              <FormLabel>Name *</FormLabel>
              <FormInput>
                <Input {...field} />
              </FormInput>
              <FormMessage />
            </div>
          );
        }}
      />

      <FormField
        name="description"
        render={({ field }) => (
          <div>
            <FormLabel>Description</FormLabel>
            <FormInput>
              <MarkdownEditor {...field} onChange={(value: string) => field.onChange(value)} />
            </FormInput>
          </div>
        )}
      />

      <FormField
        name="reviewers"
        render={({ field }) => (
          <div>
            <FormLabel>Reviewers</FormLabel>
            <FormInput>
              <Select
                multiple
                options={
                  getAllAccountsData?.[ACCOUNT_GENERIC_OBJECT]?.edges.map((edge: any) => ({
                    id: edge?.node.id,
                    name: edge?.node?.display_label,
                  })) ?? []
                }
                {...field}
              />
            </FormInput>
          </div>
        )}
      />

      <div className="text-right">
        <LinkButton variant="outline" to={constructPath("/proposed-changes")} className="mr-2">
          Cancel
        </LinkButton>

        <FormSubmit>Create proposed change</FormSubmit>
      </div>

      {error && (
        <div className="bg-red-100 p-4 text-red-800 rounded-md text-sm">{error.message}</div>
      )}
    </Form>
  );
};
