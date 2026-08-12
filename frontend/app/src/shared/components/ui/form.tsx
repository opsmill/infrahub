import { Button, type ButtonProps, DismissGuardContext } from "@infrahub/ui";
import { Slot } from "@radix-ui/react-slot";
import React from "react";
import {
  Controller,
  type ControllerProps,
  FormProvider,
  type UseFormReturn,
  useForm,
  useFormContext,
  useFormState,
} from "react-hook-form";

import { ModalConfirm } from "@/shared/components/modals/modal-confirm";
import Label, { type LabelProps } from "@/shared/components/ui/label";
import { inputErrorStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

export type FormRef = ReturnType<typeof useForm>;

export interface FormProps extends Omit<React.FormHTMLAttributes<HTMLFormElement>, "onSubmit"> {
  onSubmit?: (v: Record<string, any>) => void;
  onCancel?: () => void;
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
  onCancel,
  ref,
  ...props
}: FormProps) => {
  const currentForm = form ?? useForm({ defaultValues });

  const dismissGuard = React.use(DismissGuardContext);
  const [showConfirm, setShowConfirm] = React.useState(false);

  React.useImperativeHandle(ref, () => currentForm);

  React.useEffect(() => {
    if (!form) currentForm.reset(defaultValues);
  }, [JSON.stringify(defaultValues)]);

  const isDirty = currentForm.formState.isDirty;
  React.useEffect(() => {
    dismissGuard?.setDismissable(!isDirty, () => setShowConfirm(true));
  }, [isDirty]);

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

      <ModalConfirm
        isOpen={showConfirm}
        onOpenChange={setShowConfirm}
        title="Closing form"
        description="Are you sure you want to close this form? All unsaved changes will be lost."
        onConfirm={() => {
          setShowConfirm(false);
          dismissGuard?.setDismissable(true);
          onCancel?.();
        }}
      />
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
  const { getFieldState } = useFormContext();
  const { id, name } = React.use(FormFieldContext);
  const formState = useFormState({ name });
  const { error } = getFieldState(name, formState);
  // Flag the input only for this field's own error. A field that merely contains a
  // nested child field's error (e.g. a from-pool allocation's prefix-length field)
  // gets a nested error object with no top-level `type`, so its primary input must
  // not light up for an error the child already surfaces.
  const hasOwnError = Boolean(error?.type);

  return (
    <Slot
      ref={ref}
      id={id}
      className={classNames(hasOwnError && inputErrorStyle, className)}
      aria-invalid={hasOwnError}
      {...props}
    />
  );
};

/**
 * Returns the first error message found in a react-hook-form error object,
 * descending into nested child-field errors (e.g. a from-pool allocation's
 * prefix-length field) so a field's message area can surface a sub-field's error
 * full-width.
 */
export const findErrorMessage = (error: unknown): string | undefined => {
  if (!error || typeof error !== "object") return;
  const entry = error as { message?: unknown; [key: string]: unknown };
  if (typeof entry.message === "string" && entry.message) return entry.message;
  for (const key of Object.keys(entry)) {
    if (key === "ref" || key === "type" || key === "message") continue;
    const nested = findErrorMessage(entry[key]);
    if (nested) return nested;
  }
  return;
};

export const FormMessage = ({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) => {
  const { getFieldState } = useFormContext();
  const { name } = React.use(FormFieldContext);
  const formState = useFormState({ name });
  const { error } = getFieldState(name, formState);

  const message = findErrorMessage(error) ?? children;

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

  return <Button isPending={isLoading} {...props} type="submit" />;
};
