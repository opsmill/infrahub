import { FieldValues, SubmitHandler } from "react-hook-form";
import { DynamicFieldData } from "./dynamic-control-types";
import { Form } from "./form";

interface Props {
  fields: DynamicFieldData[];
  onSubmit: SubmitHandler<FieldValues>;
}

export default function EditFormHookComponent(props: Props) {
  return (
    <div>
      <Form onSubmit={props.onSubmit} fields={props.fields} />
    </div>
  );
}
