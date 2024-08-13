import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import { classNames } from "@/utils/common";
import { Slot } from "@radix-ui/react-slot";
import React, {
  createContext,
  FormHTMLAttributes,
  HTMLAttributes,
  useContext,
  useEffect,
  useId,
} from "react";
import {
  Controller,
  ControllerProps,
  FormProvider,
  useForm,
  useFormContext,
  UseFormReturn,
} from "react-hook-form";
import { Spinner } from "@/components/ui/spinner";
import Label, { LabelProps } from "@/components/ui/label";

export interface FormProps extends Omit<FormHTMLAttributes<HTMLFormElement>, "onSubmit"> {
  onSubmit?: (v: Record<string, any>) => void;
  defaultValues?: Partial<Record<string, unknown>>;
  form?: UseFormReturn;
}

export const Form = ({
  form,
  defaultValues,
  className,
  children,
  onSubmit,
  ...props
}: FormProps) => {
  const currentForm = form ?? useForm({ defaultValues });

  useEffect(() => {
    currentForm.reset(defaultValues);
  }, [JSON.stringify(defaultValues), currentForm.formState.isSubmitSuccessful]);

  return (
    <FormProvider {...currentForm}>
      <form
        onSubmit={(event) => {
          if (event && event.stopPropagation) {
            event.stopPropagation();
          }

          if (!onSubmit) return;

          currentForm.handleSubmit(onSubmit)(event);
        }}
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
      <Controller control={control} {...props} shouldUnregister />
    </FormFieldContext.Provider>
  );
};

export const FormLabel = ({ ...props }: LabelProps) => {
  const { id } = useContext(FormFieldContext);

  return <Label htmlFor={id} {...props} />;
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

  const message = error?.message?.toString() ?? children;
  if (!message) return null;

  return (
    <p
      className={classNames(
        "absolute -bottom-4 left-2 text-xs mt-1 italic text-gray-600",
        error && "text-red-600",
        className
      )}
      data-cy={error && "field-error-message"}
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
      <Button ref={ref} disabled={isLoading} {...props} type="submit" data-cy="submit-form">
        <span className={classNames(isLoading && "invisible")}>{children}</span>
        {isLoading && <Spinner className="absolute" />}
      </Button>
    );
  }
);
