import { Link, Navigate } from "react-router-dom";
import { usePermission } from "../../hooks/usePermission";
import { constructPath } from "../../utils/fetch";
import Content from "../layout/content";
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
import { gql, useMutation } from "@apollo/client";
import useQuery from "../../hooks/useQuery";
import { CREATE_PROPOSED_CHANGE } from "../../graphql/mutations/proposed-changes/createProposedChange";
import { useAuth } from "../../hooks/useAuth";

export const ProposedChangesCreatePage = () => {
  const permission = usePermission();

  if (!permission.write.allow) {
    return <Navigate to={constructPath("/proposed-changes")} replace />;
  }

  return (
    <Content className="p-2 py-4 max-w-2xl m-auto">
      <h1 className="text-xl font-semibold text-gray-700">Create a proposed change</h1>
      <p className="text-xs text-gray-700 mb-6">
        A proposed change lets you compare two branches, run tests, and finally merge one branch
        into another.
      </p>

      <ProposedChangeCreateForm />
    </Content>
  );
};

const ProposedChangeCreateForm = () => {
  const { user } = useAuth();
  const branches = useAtomValue(branchesState);
  const defaultBranch = branches.filter((branch) => branch.is_default);
  const sourceBranches = branches.filter((branch) => !branch.is_default);
  const form = useForm();

  const GET_ALL_ACCOUNTS = gql`
    query GetBranches {
      CoreAccount {
        edges {
          node {
            id
            display_label
          }
        }
      }
    }
  `;

  const { data: getAllAccountsData } = useQuery(GET_ALL_ACCOUNTS);

  const [createProposedChange, { loading, error }] = useMutation(CREATE_PROPOSED_CHANGE);
  return (
    <FormProvider {...form}>
      <form
        onSubmit={form.handleSubmit(
          ({ source_branch, destination_branch, name, description, reviewers }) => {
            createProposedChange({
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
          }
        )}
        className="flex flex-col items-stretch gap-4">
        <div className="flex flex-wrap md:flex-nowrap items-center gap-2 justify-center w-full">
          <Card className="w-full">
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
          </Card>

          <Icon icon="mdi:arrow-bottom" className="text-xl shrink-0 md:-rotate-90 text-gray-500" />

          <Card className="w-full">
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
          </Card>
        </div>

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
