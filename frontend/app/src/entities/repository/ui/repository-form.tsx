import { useAuth } from "@/entities/authentication/ui/useAuth";
import { currentBranchAtom } from "@/entities/branches/stores";
import { createObject } from "@/entities/nodes/api/createObject";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button } from "@/shared/components/buttons/button-primitive";
import { DynamicInput } from "@/shared/components/form/dynamic-form";
import RelationshipField from "@/shared/components/form/fields/relationships/relationship.field";
import { NodeFormProps } from "@/shared/components/form/node-form";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { Card, CardProps } from "@/shared/components/ui/card";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { classNames } from "@/shared/utils/common";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";

const RepositoryForm = ({
  onSuccess,
  schema,
  currentObject,
  onSubmit,
  onCancel,
}: NodeFormProps) => {
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
      }}
    >
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

      <div className="text-right">
        {onCancel && (
          <Button variant="outline" className="mr-2" onClick={onCancel}>
            Cancel
          </Button>
        )}

        <FormSubmit>Save</FormSubmit>
      </div>
    </Form>
  );
};

const FormGroup = ({ className, ...props }: CardProps) => {
  return <Card className={classNames("shadow-xs space-y-4", className)} {...props} />;
};

export default RepositoryForm;
