import { Navigate } from "react-router-dom";
import { usePermission } from "../../hooks/usePermission";
import { constructPath } from "../../utils/fetch";
import Content from "../layout/content";
import { Card } from "../../components/ui/card";
import { Icon } from "@iconify-icon/react";
import { ButtonWithTooltip } from "../../components/buttons/button-with-tooltip";
import { useAtomValue } from "jotai/index";
import { branchesState } from "../../state/atoms/branches.atom";
import { BUTTON_TYPES } from "../../components/buttons/button";
import { branchesToSelectOptions } from "../../utils/branches";
import { FormProvider, useForm } from "react-hook-form";
import React from "react";
import { DynamicControl } from "../edit-form-hook/dynamic-control";
import { gql } from "@apollo/client";
import useQuery from "../../hooks/useQuery";

export const ProposedChangesCreatePage = () => {
  const permission = usePermission();

  if (!permission.write.allow) {
    return <Navigate to={constructPath("/proposed-changes")} replace />;
  }

  return <ProposedChangeCreateForm />;
};

const ProposedChangeCreateForm = () => {
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

  const { data } = useQuery(GET_ALL_ACCOUNTS);

  return (
    <Content>
      <Content.Title title="Add a proposed change" />

      <FormProvider {...form}>
        <form
          onSubmit={form.handleSubmit((e) => console.log(e))}
          className="flex flex-col p-2 py-4 items-stretch gap-4 max-w-2xl m-auto">
          <div className="flex flex-wrap md:flex-nowrap items-center gap-2 justify-center w-full ">
            <Card className="w-full">
              <h2 className="font-semibold">Source branch</h2>
              <p className="text-gray-600 text-sm mb-1">Select a branch to compare</p>
              <DynamicControl
                name="source_branch.value"
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

            <Icon
              icon="mdi:arrow-bottom"
              className="text-xl shrink-0 md:-rotate-90 text-gray-500"
            />

            <Card className="w-full">
              <h2 className="font-semibold">Destination branch</h2>
              <p className="text-gray-600 text-sm mb-1">It targets the default branch</p>
              <DynamicControl
                name="destination_branch.value"
                kind="String"
                type="select"
                label="Source Branch"
                value={defaultBranch[0].id}
                options={branchesToSelectOptions(defaultBranch)}
                config={{
                  validate: (value) => !!value || "Required",
                }}
                isProtected
              />
            </Card>
          </div>

          <DynamicControl
            name="name.value"
            kind="Text"
            type="text"
            label="Name"
            value=""
            config={{ validate: (value) => !!value || "Required" }}
          />

          <DynamicControl
            name="description.value"
            kind="TextArea"
            type="textarea"
            label="Description"
            value=""
            isOptional
          />

          <DynamicControl
            name="reviewers.list"
            kind="String"
            type="multiselect"
            label="Reviewers"
            options={
              data?.CoreAccount?.edges.map((edge: any) => ({
                id: edge?.node.id,
                name: edge?.node?.display_label,
              })) ?? []
            }
            value=""
            isOptional
          />

          <ButtonWithTooltip className="self-end" type="submit" buttonType={BUTTON_TYPES.MAIN}>
            Create proposed change
          </ButtonWithTooltip>
        </form>
      </FormProvider>
    </Content>
  );
};
