import { FieldValues, SubmitHandler } from "react-hook-form";
import { DynamicFieldData } from "./dynamic-control-types";
import { Form } from "./form";

interface Props {
  fields: DynamicFieldData[];
  onSubmit: SubmitHandler<FieldValues>;
  onCancel?: Function;
  isLoading?: boolean;
  submitLabel?: string;
  preventObjectsCreation?: boolean;
}

export default function EditFormHookComponent(props: Props) {
  return <Form {...props} />;
}
