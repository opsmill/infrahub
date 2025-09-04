import { Button } from "@/shared/components/buttons/button-primitive";
import { DynamicInput } from "@/shared/components/form/dynamic-form";
import RelationshipField from "@/shared/components/form/fields/relationships/relationship.field";
import { NodeFormProps } from "@/shared/components/form/node-form";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { Card, CardProps } from "@/shared/components/ui/card";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";

const RepositoryForm = ({
  onSuccess,
  schema,
  currentObject,
  onSubmit,
  onCancel,
  ...props
}: NodeFormProps) => {
  const auth = useAuth();
  const { parentSchema, parentData } = useCurrentFormContext();
  const createObject = useCreateObjectMutation();

  const fields = getFormFieldsFromSchema({
    auth,
    initialObject: currentObject,
    schema,
    parentSchema,
    parentData,
    ...props,
  });

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

        await createObject.mutateAsync(
          {
            objectKind: schema.kind as string,
            data: getCreateMutationFromFormData(fields, formData, props.objectTemplate?.id),
          },
          {
            onSuccess,
          }
        );
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
          relationship={
            { peer: "CorePasswordCredential", name: "credential", cardinality: "one" } as any
          }
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
