import { ReactElement } from "react";
import { Form } from "../../screens/edit-form-hook/form";
import { DynamicFieldData } from "../../screens/edit-form-hook/dynamic-control-types";
import { FieldValues, SubmitHandler } from "react-hook-form";

type tAddComment = {
  onSubmit: SubmitHandler<FieldValues>;
  isLoading?: boolean;
  onCancel?: Function;
  disabled?: boolean;
  additionalButtons?: ReactElement;
};

const fields: DynamicFieldData[] = [
  {
    name: "comment",
    label: "Add a comment",
    placeholder: "Add your comment here...",
    type: "textarea",
    value: "",
    config: {
      required: "Required",
    },
  },
];

export const AddComment = ({
  onSubmit,
  isLoading,
  onCancel,
  disabled,
  additionalButtons,
}: tAddComment) => {
  return (
    <Form
      onSubmit={onSubmit}
      fields={fields}
      submitLabel="Comment"
      isLoading={isLoading}
      onCancel={onCancel}
      disabled={disabled}
      additionalButtons={additionalButtons}
    />
  );
};
