import { Link, Navigate, useNavigate } from "react-router-dom";
import { usePermission } from "../../hooks/usePermission";
import { constructPath } from "../../utils/fetch";
import { Card } from "../../components/ui/card";
import { Icon } from "@iconify-icon/react";
import { ButtonWithTooltip } from "../../components/buttons/button-with-tooltip";
import { useAtomValue } from "jotai/index";
import { branchesState } from "../../state/atoms/branches.atom";
import { Button, BUTTON_TYPES } from "../../components/buttons/button";
import { branchesToSelectOptions } from "../../utils/branches";
import { FormProvider, useForm } from "react-hook-form";
import React from "react";
import { DynamicControl } from "../edit-form-hook/dynamic-control";
import { useMutation } from "@apollo/client";
import useQuery from "../../hooks/useQuery";
import { CREATE_PROPOSED_CHANGE } from "../../graphql/mutations/proposed-changes/createProposedChange";
import { useAuth } from "../../hooks/useAuth";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "../../components/utils/alert";
import { classNames } from "../../utils/common";
import Content from "../layout/content";
import { GET_ALL_ACCOUNTS } from "../../graphql/queries/accounts/getAllAccounts";

const ProposedChangesCreatePage = () => {
  const permission = usePermission();

  if (!permission.write.allow) {
    return <Navigate to={constructPath("/proposed-changes")} replace />;
  }

  return (
    <Content>
      <div className="p-4 px-8 max-w-2xl m-auto mt-0 md:mt-4 bg-white rounded-md">
        <h1 className="text-xl font-semibold text-gray-700">Create a proposed change</h1>
        <p className="text-xs text-gray-700 mb-6">
          A proposed change lets you compare two branches, run tests, and finally merge one branch
          into another.
        </p>

        <ProposedChangeCreateForm />
      </div>
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
                source_branch,
                destination_branch,
                name,
                description,
                reviewers: reviewers.map((id: string) => ({ id })),
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
        <Card className="flex flex-wrap md:flex-nowrap items-center gap-4 justify-center w-full shadow-sm">
          <div className="w-full">
            <DynamicControl
              name="source_branch"
              kind="String"
              type="select"
              label="Source Branch"
              value=""
              options={branchesToSelectOptions(sourceBranches)}
              config={{
                validate: (value) => !!value || "Required",
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
            isOptional
          />
        </div>

        <div className="self-end align-middle">
          <Link to={constructPath("/proposed-changes")} className="mr-2">
            <Button>Cancel</Button>
          </Link>
          <ButtonWithTooltip type="submit" buttonType={BUTTON_TYPES.MAIN} disabled={loading}>
            Create proposed change
          </ButtonWithTooltip>
        </div>

        {error && (
          <div className="bg-red-100 p-4 text-red-800 rounded-md text-sm">{error.message}</div>
        )}
      </form>
    </FormProvider>
  );
};

export default ProposedChangesCreatePage;
