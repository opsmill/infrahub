import { Icon } from "@iconify-icon/react";
import { LinkButton, Spinner } from "@infrahub/ui";
import { Card, CardContent } from "@infrahub/ui/card";
import { useAtomValue } from "jotai";
import { useQueryState } from "nuqs";
import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "react-toastify";

import { BranchStatus } from "@/shared/api/graphql/generated/types";
import { constructPath } from "@/shared/api/rest/fetch";
import { MarkdownEditor } from "@/shared/components/editor/markdown";
import { RelationshipManyInput } from "@/shared/components/inputs/relationship-many";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { Form, FormField, FormInput, FormLabel, FormMessage } from "@/shared/components/ui/form";
import { Input } from "@/shared/components/ui/input";
import { PROPOSED_CHANGES_OBJECT } from "@/shared/config/constants";
import { QSP } from "@/shared/config/qsp";

import { branchesState } from "@/entities/branches/stores";
import { branchesToSelectOptions } from "@/entities/branches/utils";
import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { DRAFT_STATE, OPEN_STATE } from "@/entities/proposed-changes/constants";
import { useCreateProposedChange } from "@/entities/proposed-changes/ui/queries/create-proposed-change.mutation";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { PcStateButton } from "./action-button/pc-state-button";

export const ProposedChangeCreateForm = () => {
  const [sourceBranch] = useQueryState(QSP.SOURCE_BRANCH);
  const branches = useAtomValue(branchesState);
  const defaultBranch = branches.find((branch) => branch.is_default);
  const sourceBranches = branches.filter(
    (branch) => !branch.is_default && branch.status !== BranchStatus.MERGED
  );
  const navigate = useNavigate();
  const [state, setState] = useState(OPEN_STATE);

  const { schema: proposedChangeSchema } = useSchema(PROPOSED_CHANGES_OBJECT);

  const { mutateAsync: createProposedChange, error } = useCreateProposedChange();

  if (branches.length === 0 || !proposedChangeSchema) {
    return <Spinner className="flex justify-center" />;
  }

  return (
    <Form
      onSubmit={async ({ source_branch, destination_branch, name, description, reviewers }) => {
        const result = await createProposedChange({
          source_branch,
          destination_branch,
          name,
          description,
          isDraft: state === DRAFT_STATE,
          reviewers: reviewers?.map((node: Node) => ({ id: node.id })) || [],
        });

        toast(<Alert type={ALERT_TYPES.SUCCESS} message="Proposed change created" />, {
          toastId: "alert-success-CoreProposedChange-created",
        });

        const url = constructPath(`/proposed-changes/${result.id}`);
        navigate(url);
      }}
    >
      <Card className="w-full border-gray-300 shadow-xs">
        <CardContent className="flex flex-row flex-wrap items-start justify-center gap-4 md:flex-nowrap">
          <FormField
            name="source_branch"
            defaultValue={sourceBranch}
            rules={{
              required: "Required",
              validate: {
                branchExists: (value: string) => {
                  if (sourceBranches.some((b) => b.name === value)) {
                    return true;
                  }

                  if (branches.some((b) => b.name === value)) {
                    return "Branch is not available (merged or default)";
                  }

                  return "Branch does not exist";
                },
              },
            }}
            render={({ field }) => {
              const fieldData: string | null = field.value;

              return (
                <div className="relative mb-2 flex w-full flex-col">
                  <FormLabel>Source Branch *</FormLabel>
                  <Combobox>
                    <FormInput>
                      <ComboboxTrigger>{fieldData}</ComboboxTrigger>
                    </FormInput>

                    <ComboboxContent>
                      <ComboboxList>
                        <ComboboxEmpty>No branch found</ComboboxEmpty>

                        {branchesToSelectOptions(sourceBranches).map(({ name }) => (
                          <ComboboxItem
                            key={name}
                            value={name}
                            selectedValue={fieldData}
                            onSelect={() => field.onChange(name)}
                          >
                            {name}
                          </ComboboxItem>
                        ))}
                      </ComboboxList>
                    </ComboboxContent>
                  </Combobox>
                  <FormMessage />
                </div>
              );
            }}
          />

          <Icon
            icon="mdi:arrow-bottom"
            className="shrink-0 text-gray-500 text-xl md:mt-8 md:-rotate-90"
          />

          <FormField
            name="destination_branch"
            defaultValue={defaultBranch?.name}
            rules={{ required: "Required" }}
            render={({ field }) => (
              <div className="relative mb-2 flex w-full flex-col">
                <FormLabel>Destination Branch *</FormLabel>
                <Combobox>
                  <FormInput>
                    <ComboboxTrigger disabled>{field.value}</ComboboxTrigger>
                  </FormInput>
                </Combobox>
                <FormMessage />
              </div>
            )}
          />
        </CardContent>
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
              <RelationshipManyInput
                {...field}
                peer={
                  proposedChangeSchema.relationships?.find((rel) => rel.name === "reviewers")
                    ?.peer ?? ""
                }
              />
            </FormInput>
          </div>
        )}
      />

      <div className="flex w-full items-center justify-end gap-2">
        <LinkButton variant="outline" href={constructPath("/proposed-changes")}>
          Cancel
        </LinkButton>

        <PcStateButton state={state} setState={setState} />
      </div>

      {error && (
        <div className="rounded-md bg-red-100 p-4 text-red-800 text-sm">
          {(error as Error).message}
        </div>
      )}
    </Form>
  );
};
