import { Slot } from "@radix-ui/react-slot";
import React, {
  createContext,
  type FormHTMLAttributes,
  type HTMLAttributes,
  use,
  useEffect,
  useId,
  useImperativeHandle,
} from "react";
import {
  Controller,
  type ControllerProps,
  FormProvider,
  type UseFormReturn,
  useForm,
  useFormContext,
} from "react-hook-form";

import { Button, type ButtonProps } from "@/shared/components/buttons/button-primitive";
import { SlideOverContext } from "@/shared/components/display/slide-over";
import Label, { type LabelProps } from "@/shared/components/ui/label";
import { Spinner } from "@/shared/components/ui/spinner";
import { classNames } from "@/shared/utils/common";

export type FormRef = ReturnType<typeof useForm>;

export interface FormProps extends Omit<FormHTMLAttributes<HTMLFormElement>, "onSubmit"> {
  onSubmit?: (v: Record<string, any>) => void;
  defaultValues?: Partial<Record<string, unknown>>;
  form?: UseFormReturn;
}

export const Form = React.forwardRef<FormRef, FormProps>(
  ({ form, defaultValues, className, children, onSubmit, ...props }: FormProps, ref) => {
    const currentForm = form ?? useForm({ defaultValues });

    const slideOverContext = use(SlideOverContext);

    useImperativeHandle(ref, () => currentForm);

    useEffect(() => {
      if (!form) currentForm.reset(defaultValues);
    }, [JSON.stringify(defaultValues)]);

    useEffect(() => {
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
  }
);

type FormFieldContextType = { id: string; name: string };
const FormFieldContext = createContext<FormFieldContextType>({} as FormFieldContextType);

export const FormField = (props: ControllerProps) => {
  const { control } = useFormContext();
  const id = useId();

  return (
    <FormFieldContext value={{ id, name: props.name }}>
      <Controller control={control} shouldUnregister {...props} />
    </FormFieldContext>
  );
};

export const FormLabel = ({ ...props }: LabelProps) => {
  const { id } = use(FormFieldContext);

  return <Label htmlFor={id} {...props} />;
};

export const FormInput = React.forwardRef<
  React.ElementRef<typeof Slot>,
  React.ComponentPropsWithoutRef<typeof Slot>
>(({ className, ...props }, ref) => {
  const { getFieldState, formState } = useFormContext();
  const { id, name } = use(FormFieldContext);
  const { error } = getFieldState(name, formState);

  return (
    <Slot
      ref={ref}
      id={id}
      className={classNames(
        error &&
          "border-red-500 focus-within:border-red-500 focus-within:ring-red-500/25 focus:border-red-500 focus:ring-red-500/25 focus-visible:border-red-500 focus-visible:ring-red-500/25",
        className
      )}
      aria-invalid={!!error}
      {...props}
    />
  );
});

export const FormMessage = ({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) => {
  const { getFieldState, formState } = useFormContext();
  const { name } = use(FormFieldContext);

  const { error } = getFieldState(name, formState);

  const message = error?.message?.toString() ?? children;

  if (!message) return null;

  return (
    <p
      className={classNames("text-gray-600 text-sm", error && "text-red-600", className)}
      data-cy={error && "field-error-message"}
      {...props}
    >
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
