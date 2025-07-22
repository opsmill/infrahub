import { PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { branchesState } from "@/entities/branches/stores";
import { branchesToSelectOptions } from "@/entities/branches/utils";
import { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { CREATE_PROPOSED_CHANGE } from "@/entities/proposed-changes/api/createProposedChange";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { useMutation } from "@/shared/api/graphql/useQuery";
import { constructPath } from "@/shared/api/rest/fetch";
import { LinkButton } from "@/shared/components/buttons/button-primitive";
import { MarkdownEditor } from "@/shared/components/editor/markdown";
import { RelationshipManyInput } from "@/shared/components/inputs/relationship-many";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Card } from "@/shared/components/ui/card";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import {
  Form,
  FormField,
  FormInput,
  FormLabel,
  FormMessage,
  FormSubmit,
} from "@/shared/components/ui/form";
import { Input } from "@/shared/components/ui/input";
import { Spinner } from "@/shared/components/ui/spinner";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useNavigate } from "react-router";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";

export const ProposedChangeCreateForm = () => {
  const [sourceBranch] = useQueryParam(QSP.SOURCE_BRANCH, StringParam);
  const branches = useAtomValue(branchesState);
  const defaultBranch = branches.find((branch) => branch.is_default);
  const sourceBranches = branches.filter((branch) => !branch.is_default);
  const navigate = useNavigate();

  const { schema: proposedChangeSchema } = useSchema(PROPOSED_CHANGES_OBJECT);

  const [createProposedChange, { error }] = useMutation(CREATE_PROPOSED_CHANGE);

  if (branches.length === 0 || !proposedChangeSchema)
    return <Spinner className="flex justify-center" />;

  return (
    <Form
      onSubmit={async ({ source_branch, destination_branch, name, description, reviewers }) => {
        const { data } = await createProposedChange({
          variables: {
            source_branch,
            destination_branch,
            name,
            description,
            reviewers: reviewers?.map((node: Node) => ({ id: node.id })) || [],
          },
        });

        toast(<Alert type={ALERT_TYPES.SUCCESS} message="Proposed change created" />, {
          toastId: "alert-success-CoreProposedChange-created",
        });

        const url = constructPath(`/proposed-changes/${data.CoreProposedChangeCreate.object.id}`);
        navigate(url);
      }}
    >
      <Card className="flex flex-wrap md:flex-nowrap items-start gap-4 justify-center w-full shadow-xs border-gray-300">
        <FormField
          name="source_branch"
          defaultValue={sourceBranch}
          rules={{
            required: "Required",
            validate: {
              branchExists: (value: string) => {
                const branchesName = sourceBranches.map(({ name }) => name);
                return branchesName.includes(value) || "Branch does not exist";
              },
            },
          }}
          render={({ field }) => {
            const fieldData: string | null = field.value;

            return (
              <div className="w-full relative mb-2 flex flex-col">
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
          className="text-xl md:mt-8 shrink-0 md:-rotate-90 text-gray-500"
        />

        <FormField
          name="destination_branch"
          defaultValue={defaultBranch?.name}
          rules={{ required: "Required" }}
          render={({ field }) => (
            <div className="w-full relative mb-2 flex flex-col">
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
