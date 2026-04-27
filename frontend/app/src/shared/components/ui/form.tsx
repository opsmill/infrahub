import { Slot } from "@radix-ui/react-slot";
import React from "react";
import {
  Controller,
  type ControllerProps,
  FormProvider,
  type UseFormReturn,
  useForm,
  useFormContext,
} from "react-hook-form";

import { Button, type ButtonProps } from "@/shared/components/aria/button";
import { SlideOverContext } from "@/shared/components/display/slide-over";
import Label, { type LabelProps } from "@/shared/components/ui/label";
import { inputErrorStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

export type FormRef = ReturnType<typeof useForm>;

export interface FormProps extends Omit<React.FormHTMLAttributes<HTMLFormElement>, "onSubmit"> {
  onSubmit?: (v: Record<string, any>) => void;
  defaultValues?: Partial<Record<string, unknown>>;
  form?: UseFormReturn;
  ref?: React.Ref<FormRef>;
}

export const Form = ({
  form,
  defaultValues,
  className,
  children,
  onSubmit,
  ref,
  ...props
}: FormProps) => {
  const currentForm = form ?? useForm({ defaultValues });

  const slideOverContext = React.use(SlideOverContext);

  React.useImperativeHandle(ref, () => currentForm);

  React.useEffect(() => {
    if (!form) currentForm.reset(defaultValues);
  }, [JSON.stringify(defaultValues)]);

  React.useEffect(() => {
    // Stop logic if there is no context to prevent the slide over close
    if (!slideOverContext?.setPreventClose) return;

    slideOverContext.setPreventClose(currentForm.formState.isDirty);
  }, [currentForm.formState.isDirty]);

  return (
    <FormProvider {...currentForm}>
      <form
        onSubmit={(event) => {
          if (event && event.stopPropagation) {
            event.stopPropagation();
          }

          if (onSubmit) {
            currentForm.handleSubmit(async (data) => {
              await onSubmit(data);
              currentForm.reset(data);
            })(event);
          }
        }}
        className={classNames("space-y-4", className)}
        {...props}
      >
        {children}
      </form>
    </FormProvider>
  );
};

type FormFieldContextType = { id: string; name: string };
const FormFieldContext = React.createContext<FormFieldContextType>({} as FormFieldContextType);

export const FormField = (props: ControllerProps) => {
  const { control } = useFormContext();
  const id = React.useId();

  return (
    <FormFieldContext value={{ id, name: props.name }}>
      <Controller control={control} shouldUnregister {...props} />
    </FormFieldContext>
  );
};

export const FormLabel = ({ ...props }: LabelProps) => {
  const { id } = React.use(FormFieldContext);

  return <Label htmlFor={id} {...props} />;
};

interface FormInputProps extends React.ComponentProps<typeof Slot> {}

export const FormInput = ({ className, ref, ...props }: FormInputProps) => {
  const { getFieldState, formState } = useFormContext();
  const { id, name } = React.use(FormFieldContext);
  const { error } = getFieldState(name, formState);

  return (
    <Slot
      ref={ref}
      id={id}
      className={classNames(error && inputErrorStyle, className)}
      aria-invalid={!!error}
      {...props}
    />
  );
};

export const FormMessage = ({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) => {
  const { getFieldState, formState } = useFormContext();
  const { name } = React.use(FormFieldContext);

  const { error } = getFieldState(name, formState);

  const message = error?.message?.toString() ?? children;

  if (!message) return null;

  return (
    <p
      className={classNames("text-gray-600 text-sm", error && "text-red-600", className)}
      {...props}
    >
      {message}
    </p>
  );
};

interface FormSubmitProps extends Omit<ButtonProps, "type" | "slot"> {}

export const FormSubmit = ({ ...props }: FormSubmitProps) => {
  const { formState } = useFormContext();

  const isLoading = formState.isSubmitting || formState.isValidating;

  return <Button isPending={isLoading} {...props} type="submit" slot={null} />;
};
