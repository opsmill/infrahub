import { useMutation } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { Button } from "../../components/buttons/button-primitive";
import { MarkdownEditor } from "../../components/editor";
import { Select } from "../../components/inputs/select";
import { ALERT_TYPES, Alert } from "../../components/ui/alert";
import { Card } from "../../components/ui/card";
import { Combobox } from "../../components/ui/combobox";
import { Form, FormField, FormInput, FormLabel, FormMessage } from "../../components/ui/form";
import { Input } from "../../components/ui/input";
import { CREATE_PROPOSED_CHANGE } from "../../graphql/mutations/proposed-changes/createProposedChange";
import { GET_ALL_ACCOUNTS } from "../../graphql/queries/accounts/getAllAccounts";
import { useAuth } from "../../hooks/useAuth";
import { usePermission } from "../../hooks/usePermission";
import useQuery from "../../hooks/useQuery";
import { branchesState } from "../../state/atoms/branches.atom";
import { branchesToSelectOptions } from "../../utils/branches";
import { constructPath } from "../../utils/fetch";
import Content from "../layout/content";

const ProposedChangesCreatePage = () => {
  const permission = usePermission();

  if (!permission.write.allow) {
    return <Navigate to={constructPath("/proposed-changes")} replace />;
  }

  return (
    <Content>
      <Card className="p-4 px-8 max-w-2xl m-auto mt-0 md:mt-4">
        <h1 className="text-xl font-semibold text-gray-700">Create a proposed change</h1>
        <p className="text-xs text-gray-700 mb-6">
          A proposed change lets you compare two branches, run tests, and finally merge one branch
          into another.
        </p>

        <ProposedChangeCreateForm />
      </Card>
    </Content>
  );
};

export const ProposedChangeCreateForm = () => {
  const { user } = useAuth();
  const branches = useAtomValue(branchesState);
  const defaultBranch = branches.filter((branch) => branch.is_default);
  const sourceBranches = branches.filter((branch) => !branch.is_default);
  const navigate = useNavigate();

  const { data: getAllAccountsData } = useQuery(GET_ALL_ACCOUNTS);

  const [createProposedChange, { loading, error }] = useMutation(CREATE_PROPOSED_CHANGE);

  return (
    <Form
      className="space-y-4"
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

        toast(() => <Alert type={ALERT_TYPES.SUCCESS} message="Proposed change created" />, {
          toastId: "alert-success-CoreProposedChange-created",
        });

        const url = constructPath(`/proposed-changes/${data.CoreProposedChangeCreate.object.id}`);
        navigate(url);
      }}>
      <Card className="flex flex-wrap md:flex-nowrap items-start gap-4 justify-center w-full shadow-sm border-gray-300">
        <FormField
          name="source_branch"
          defaultValue=""
          rules={{
            required: true,
            validate: {
              branchExists: (value: string) => {
                const branchesName = sourceBranches.map(({ name }) => name);
                return branchesName.includes(value) || "Branch does not exist";
              },
            },
          }}
          render={({ field }) => (
            <div className="w-full">
              <FormLabel>Source Branch *</FormLabel>
              <FormInput>
                <Combobox
                  {...field}
                  placeholder="Select a branch..."
                  items={branchesToSelectOptions(sourceBranches).map(({ name }) => name)}
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
          defaultValue={defaultBranch[0].name}
          rules={{ required: true }}
          render={({ field }) => (
            <div className="w-full">
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
        rules={{ required: true }}
        render={({ field }) => {
          return (
            <div>
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
                  getAllAccountsData?.CoreAccount?.edges.map((edge: any) => ({
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
        <Link to={constructPath("/proposed-changes")} className="mr-2">
          <Button variant="outline">Cancel</Button>
        </Link>

        <Button type="submit" disabled={loading}>
          Create proposed change
        </Button>
      </div>

      {error && (
        <div className="bg-red-100 p-4 text-red-800 rounded-md text-sm">{error.message}</div>
      )}
    </Form>
  );
};

export default ProposedChangesCreatePage;
