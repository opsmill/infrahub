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

const RepositoryForm = ({ onSuccess, schema, currentObject, onSubmit }: NodeFormProps) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const auth = useAuth();
  const fields = getFormFieldsFromSchema({ auth, schema, initialObject: currentObject });

  const gitUrlFieldProps = fields.find(({ name }) => name === "location");
  const credentialFieldProps = fields.find(({ name }) => name === "credential");

  const nameFieldProps = fields.find(({ name }) => name === "name");
  const descriptionFieldProps = fields.find(({ name }) => name === "description");

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
            label="URL of a Git repository"
            placeholder="https://github.com/organization/project.git"
          />
        )}

        {credentialFieldProps && <DynamicInput {...credentialFieldProps} />}
      </FormGroup>

      <FormGroup>
        {nameFieldProps && <DynamicInput {...nameFieldProps} />}
        {descriptionFieldProps && <DynamicInput {...descriptionFieldProps} />}
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
