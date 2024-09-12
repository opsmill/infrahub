import { Form, FormSubmit } from "@/components/ui/form";
import { Card, CardProps } from "@/components/ui/card";
import { classNames } from "@/utils/common";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { useAtomValue } from "jotai/index";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { getCreateMutationFromFormData } from "@/components/form/utils/mutations/getCreateMutationFromFormData";
import { getFormFieldsFromSchema } from "@/components/form/utils/getFormFieldsFromSchema";
import { useAuth } from "@/hooks/useAuth";
import { DynamicInput } from "@/components/form/dynamic-form";
import { NodeFormProps } from "@/components/form/node-form";
import { createObject } from "@/graphql/mutations/objects/createObject";
import RelationshipField from "@/components/form/fields/relationship.field";

const RepositoryForm = ({ onSuccess, schema, currentObject, onSubmit }: NodeFormProps) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const auth = useAuth();
  const fields = getFormFieldsFromSchema({ auth, schema, initialObject: currentObject });

  const gitUrlFieldProps = fields.find(({ name }) => name === "location");

  const nameFieldProps = fields.find(({ name }) => name === "name");
  const descriptionFieldProps = fields.find(({ name }) => name === "description");

  // 1 of those 2 fields will be choosen depending on the read only or regular repository
  const refFieldProps = fields.find(({ name }) => name === "ref");
  const defaultBranchFieldProps = fields.find(({ name }) => name === "default_branch");

  const tagsFieldProps = fields.find(({ name }) => name === "tags");

  return (
    <Form
      className="p-2 bg-stone-100 h-full overflow-auto"
      onSubmit={async (formData) => {
        if (onSubmit) return onSubmit({ formData, fields });

        const data = getCreateMutationFromFormData(fields, formData);

        const mutation = gql(
          createObject({
            kind: schema?.kind,
            data: stringifyWithoutQuotes(data),
          })
        );

        const result = await graphqlClient.mutate({
          mutation,
          context: {
            branch: branch?.name,
            date,
          },
        });

        await graphqlClient.reFetchObservableQueries();
        if (onSuccess) await onSuccess(result?.data?.[`${schema?.kind}Create`]);
      }}>
      <FormGroup>
        {gitUrlFieldProps && (
          <DynamicInput
            {...gitUrlFieldProps}
            label="Repository location"
            placeholder="https://github.com/organization/project.git"
          />
        )}

        <RelationshipField
          name="credential"
          type="relationship"
          label="Authentication"
          placeholder="Select your credential"
          relationship={{ peer: "CorePasswordCredential", name: "credential", cardinality: "one" }}
          schema={schema}
        />
      </FormGroup>

      <FormGroup>
        {nameFieldProps && <DynamicInput {...nameFieldProps} placeholder="example-name" />}
        {descriptionFieldProps && (
          <DynamicInput {...descriptionFieldProps} placeholder="Add your description here..." />
        )}
      </FormGroup>

      <FormGroup>
        {refFieldProps && <DynamicInput {...refFieldProps} />}
        {defaultBranchFieldProps && <DynamicInput {...defaultBranchFieldProps} />}
      </FormGroup>

      {tagsFieldProps && (
        <FormGroup>
          <DynamicInput {...tagsFieldProps} />
        </FormGroup>
      )}

      <FormSubmit className="float-right">Save</FormSubmit>
    </Form>
  );
};

const FormGroup = ({ className, ...props }: CardProps) => {
  return <Card className={classNames("shadow-sm space-y-4", className)} {...props} />;
};

export default RepositoryForm;
