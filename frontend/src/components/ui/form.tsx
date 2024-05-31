import React, { createContext, FormHTMLAttributes, HTMLAttributes, useContext, useId } from "react";
import {
  Controller,
  ControllerProps,
  FormProvider,
  useForm,
  useFormContext,
} from "react-hook-form";
import * as LabelPrimitive from "@radix-ui/react-label";
import { Slot } from "@radix-ui/react-slot";
import { classNames } from "../../utils/common";

interface FormProps extends Omit<FormHTMLAttributes<HTMLFormElement>, "onSubmit"> {
  onSubmit?: (v: Record<string, any>) => void;
}

export const Form = ({ onSubmit, children, ...props }: FormProps) => {
  const form = useForm();

  return (
    <FormProvider {...form}>
      <form onSubmit={onSubmit && form.handleSubmit(onSubmit)} {...props}>
        {children}
      </form>
    </FormProvider>
  );
};

type FormFieldContextType = { id: string; name: string };
const FormFieldContext = createContext<FormFieldContextType>({} as FormFieldContextType);

export const FormField = (props: ControllerProps) => {
  const { control } = useFormContext();
  const id = useId();

  return (
    <FormFieldContext.Provider value={{ id, name: props.name }}>
      <Controller control={control} {...props} />
    </FormFieldContext.Provider>
  );
};

export const FormLabel = ({ className, ...props }: LabelPrimitive.LabelProps) => {
  const { id, name } = useContext(FormFieldContext);
  const { getFieldState, formState } = useFormContext();

  const { error } = getFieldState(name, formState);

  return (
    <LabelPrimitive.Label
      htmlFor={id}
      className={classNames(
        "text-sm font-medium leading-6 text-gray-900",
        error && "text-red-600",
        className
      )}
      {...props}
    />
  );
};

export const FormInput = React.forwardRef<
  React.ElementRef<typeof Slot>,
  React.ComponentPropsWithoutRef<typeof Slot>
>(({ ...props }, ref) => {
  const { id } = useContext(FormFieldContext);

  return <Slot ref={ref} id={id} {...props} />;
});

export const FormMessage = ({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) => {
  const { getFieldState, formState } = useFormContext();
  const { name } = useContext(FormFieldContext);

  const { error } = getFieldState(name, formState);

  const message = error?.type === "required" ? "Required" : error?.message?.toString() ?? children;
  if (!message) return null;

  return (
    <p className={classNames("ml-1 text-sm", error && "text-red-600", className)} {...props}>
      {message}
    </p>
  );
};
