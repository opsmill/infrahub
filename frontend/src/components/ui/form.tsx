import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import { classNames } from "@/utils/common";
import * as LabelPrimitive from "@radix-ui/react-label";
import { Slot } from "@radix-ui/react-slot";
import React, { createContext, FormHTMLAttributes, HTMLAttributes, useContext, useId } from "react";
import {
  Controller,
  ControllerProps,
  FormProvider,
  useForm,
  useFormContext,
} from "react-hook-form";
import { Spinner } from "./spinner";

export interface FormProps extends Omit<FormHTMLAttributes<HTMLFormElement>, "onSubmit"> {
  onSubmit?: (v: Record<string, unknown>) => void;
}

export const Form = ({ className, children, onSubmit, ...props }: FormProps) => {
  const form = useForm();

  return (
    <FormProvider {...form}>
      <form
        onSubmit={onSubmit && form.handleSubmit(onSubmit)}
        className={classNames("space-y-4", className)}
        {...props}>
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
  const { id } = useContext(FormFieldContext);

  return (
    <LabelPrimitive.Label
      htmlFor={id}
      className={classNames("text-sm font-medium text-gray-900 cursor-pointer", className)}
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
    <p
      className={classNames(
        "text-xs mt-1 italic text-gray-600",
        error && "text-red-600",
        className
      )}
      {...props}>
      {message}
    </p>
  );
};

export const FormSubmit = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ children, ...props }, ref) => {
    const { formState } = useFormContext();

    const isLoading = formState.isSubmitting || formState.isValidating;

    return (
      <Button ref={ref} disabled={isLoading} {...props} type="submit">
        <span className={classNames(isLoading && "invisible")}>{children}</span>
        {isLoading && <Spinner className="absolute" />}
      </Button>
    );
  }
);