import { ReactElement } from "react";
import { FieldValues, SubmitHandler } from "react-hook-form";
import { DynamicFieldData } from "../../screens/edit-form-hook/dynamic-control-types";
import { Form } from "../../screens/edit-form-hook/form";

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
    type: "textarea",
    value: "",
    config: {
      required: "Required",
    },
  },
];

export const AddComment = (props: tAddComment) => {
  const { onSubmit, isLoading, onCancel, disabled, additionalButtons } = props;

  return (
    <div className="mb-6">
      <div className="bg-white rounded-lg rounded-t-lg border border-gray-200 relative">
        <Form
          onSubmit={onSubmit}
          fields={fields}
          submitLabel={"Comment"}
          isLoading={isLoading}
          onCancel={onCancel}
          disabled={disabled}
          additionalButtons={additionalButtons}
        />
      </div>
    </div>
  );
};
