import { FormProvider, useForm } from "react-hook-form";
import { DynamicControl } from "../screens/edit-form-hook/dynamic-control";
import { FormProps } from "../screens/edit-form-hook/form";
import { resolve } from "../utils/objects";
import { Button } from "./buttons/button";

export const Filters = ({ fields, onSubmit }: FormProps) => {
  const formMethods = useForm();
  const {
    handleSubmit,
    formState: { errors },
  } = formMethods;

  const FilterField = (props: any) => {
    const { field, error } = props;

    return (
      <div className="p-2 mr-2">
        <DynamicControl {...field} error={error} />
      </div>
    );
  };

  return (
    <div>
      <form className="flex-1" onSubmit={handleSubmit(onSubmit)}>
        <FormProvider {...formMethods}>
          <div className="flex items-center">
            {fields.map((field: any, index: number) => (
              <FilterField key={index} field={field} error={resolve(field.name, errors)} />
            ))}
          </div>

          <div className="p-2">
            <Button type="submit">Validate</Button>
          </div>
        </FormProvider>
      </form>
    </div>
  );
};
