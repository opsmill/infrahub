import { useMutation } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { FormProvider, useForm } from "react-hook-form";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { Button } from "../../components/buttons/button-primitive";
import { Card } from "../../components/ui/card";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import { CREATE_PROPOSED_CHANGE } from "../../graphql/mutations/proposed-changes/createProposedChange";
import { GET_ALL_ACCOUNTS } from "../../graphql/queries/accounts/getAllAccounts";
import { useAuth } from "../../hooks/useAuth";
import { usePermission } from "../../hooks/usePermission";
import useQuery from "../../hooks/useQuery";
import { branchesState } from "../../state/atoms/branches.atom";
import { branchesToSelectOptions } from "../../utils/branches";
import { classNames } from "../../utils/common";
import { constructPath } from "../../utils/fetch";
import { resolve } from "../../utils/objects";
import { DynamicControl } from "../edit-form-hook/dynamic-control";
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

export const ProposedChangeCreateForm = ({ className }: { className?: string }) => {
  const { user } = useAuth();
  const branches = useAtomValue(branchesState);
  const defaultBranch = branches.filter((branch) => branch.is_default);
  const sourceBranches = branches.filter((branch) => !branch.is_default);
  const form = useForm();
  const navigate = useNavigate();

  const { data: getAllAccountsData } = useQuery(GET_ALL_ACCOUNTS);

  const [createProposedChange, { loading, error }] = useMutation(CREATE_PROPOSED_CHANGE);

  return (
    <FormProvider {...form}>
      <form
        onSubmit={form.handleSubmit(
          async ({ source_branch, destination_branch, name, description, reviewers }) => {
            const { data } = await createProposedChange({
              variables: {
                source_branch: source_branch.id,
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

            const url = constructPath(
              `/proposed-changes/${data.CoreProposedChangeCreate.object.id}`
            );
            navigate(url);
          }
        )}
        className={classNames("flex flex-col items-stretch gap-4", className)}>
        <Card className="flex flex-wrap md:flex-nowrap items-center gap-4 justify-center w-full shadow-sm border-gray-300">
          <div className="w-full">
            <DynamicControl
              name="source_branch"
              kind="String"
              type="select"
              label="Source Branch"
              value=""
              options={branchesToSelectOptions(sourceBranches)}
              error={resolve("source_branch", form.formState.errors)}
              config={{
                validate: (value) => {
                  if (!value) return "Required";

                  const branchesName = sourceBranches.map(({ name }) => name);
                  if (!branchesName.includes(value.id)) return "Branch does not exist";

                  return true;
                },
              }}
            />
          </div>

          <Icon icon="mdi:arrow-bottom" className="text-xl shrink-0 md:-rotate-90 text-gray-500" />

          <div className="w-full">
            <DynamicControl
              name="destination_branch"
              kind="String"
              type="select"
              label="Destination Branch"
              value={defaultBranch[0].name}
              options={branchesToSelectOptions(defaultBranch)}
              config={{
                validate: (value) => !!value || "Required",
              }}
              error={resolve("destination_branch", form.formState.errors)}
              isProtected
            />
          </div>
        </Card>

        <div>
          <DynamicControl
            name="name"
            kind="Text"
            type="text"
            label="Name"
            value=""
            error={resolve("name", form.formState.errors)}
            config={{ validate: (value) => !!value || "Required" }}
          />
        </div>

        <div>
          <DynamicControl
            name="description"
            kind="TextArea"
            type="textarea"
            label="Description"
            value=""
            error={resolve("description", form.formState.errors)}
            isOptional
          />
        </div>

        <div>
          <DynamicControl
            name="reviewers"
            kind="String"
            type="multiselect"
            label="Reviewers"
            options={
              getAllAccountsData?.CoreAccount?.edges.map((edge: any) => ({
                id: edge?.node.id,
                name: edge?.node?.display_label,
              })) ?? []
            }
            value={[]}
            error={resolve("reviewers", form.formState.errors)}
            isOptional
          />
        </div>

        <div className="self-end align-middle">
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
      </form>
    </FormProvider>
  );
};

export default ProposedChangesCreatePage;
