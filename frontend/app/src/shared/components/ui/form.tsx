import { Button, type ButtonProps, DismissGuardContext } from "@infrahub/ui";
import { Slot } from "@radix-ui/react-slot";
import React from "react";
import {
  Controller,
  type ControllerProps,
  type DefaultValues,
  type FieldValues,
  FormProvider,
  type UseFormProps,
  type UseFormReturn,
  useForm,
  useFormContext,
  useFormState,
} from "react-hook-form";

import { Row } from "@/shared/components/container";
import { ModalConfirm } from "@/shared/components/modals/modal-confirm";
import Label, { type LabelProps } from "@/shared/components/ui/label";
import { inputErrorStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

export type FormRef<TValues extends FieldValues = FieldValues> = UseFormReturn<TValues>;

export interface FormProps<TValues extends FieldValues = FieldValues>
  extends Omit<React.FormHTMLAttributes<HTMLFormElement>, "onSubmit"> {
  /** A rejected promise keeps the form dirty, so the user can retry; the handler reports the failure itself. */
  onSubmit?: (v: TValues) => unknown;
  onCancel?: () => void;
  defaultValues?: DefaultValues<TValues>;
  /** When the fields validate; ignored when `form` is given, since that form already has one. */
  mode?: UseFormProps<TValues>["mode"];
  form?: UseFormReturn<TValues>;
  ref?: React.Ref<FormRef<TValues>>;
}

export const Form = <TValues extends FieldValues = FieldValues>({
  form,
  defaultValues,
  mode,
  className,
  children,
  onSubmit,
  onCancel,
  ref,
  ...props
}: FormProps<TValues>) => {
  const currentForm = form ?? useForm<TValues>({ defaultValues, mode });

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
            currentForm
              .handleSubmit(async (data) => {
                await onSubmit(data);
                // Keeps errors the submit handler set, such as a refusal from the backend.
                currentForm.reset(data, { keepErrors: true });
              })(event)
              .catch((error: unknown) => console.error(error));
          }
        }}
        className={classNames(
          // A control scrolled into view at the bottom edge must land above the pinned buttons; list options keep their own scrolling.
          "space-y-6 has-[>[data-form-actions]]:[&_:is(input,textarea,select,button,[contenteditable])]:scroll-mb-16",
          className
        )}
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
      className={classNames("text-foreground-muted text-sm", error && "text-danger", className)}
      {...props}
    >
      {message}
    </p>
  );
};

interface FormActionsProps extends Omit<React.ComponentProps<"div">, "ref"> {}

// Sub-pixel layout under zoom or a scaled sheet must not read as pinned.
const PINNED_TOLERANCE_PX = 1;

// Sticky positioning treats every one of these as the area it sticks to.
const SCROLL_CONTAINER_OVERFLOW = new Set(["auto", "scroll", "overlay", "hidden"]);

const getScrollContainer = (element: HTMLElement): HTMLElement | null => {
  for (let parent = element.parentElement; parent; parent = parent.parentElement) {
    if (SCROLL_CONTAINER_OVERFLOW.has(getComputedStyle(parent).overflowY)) return parent;
  }
  return null;
};

const getVisibleBottom = (scrollContainer: HTMLElement | null) =>
  scrollContainer
    ? scrollContainer.getBoundingClientRect().top +
      scrollContainer.clientTop +
      scrollContainer.clientHeight
    : window.innerHeight;

/**
 * Keeps the form's buttons in view at the bottom of the area that scrolls the form, and draws a
 * separator while fields are scrolled out of view beneath them; render it as the form's last child.
 */
export const FormActions = ({ className, ...props }: FormActionsProps) => {
  const actionsRef = React.useRef<HTMLDivElement>(null);
  const restingBottomRef = React.useRef<HTMLDivElement>(null);
  const [isPinned, setIsPinned] = React.useState(false);

  React.useLayoutEffect(() => {
    const actions = actionsRef.current;
    const restingBottom = restingBottomRef.current;
    if (!actions || !restingBottom) return;

    const scrollContainer = getScrollContainer(actions);
    const applyScrollPadding = () =>
      actions.style.setProperty(
        "--form-actions-scroll-padding",
        scrollContainer ? getComputedStyle(scrollContainer).paddingBottom : "0px"
      );
    applyScrollPadding();

    // The marker stays where the bar rests, so the bar is pinned exactly while the marker is below the visible area.
    setIsPinned(
      restingBottom.getBoundingClientRect().top - getVisibleBottom(scrollContainer) >
        PINNED_TOLERANCE_PX
    );
    const intersectionObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const visibleBottom = entry.rootBounds?.bottom ?? getVisibleBottom(scrollContainer);
          setIsPinned(!entry.isIntersecting && entry.boundingClientRect.top > visibleBottom);
        }
      },
      { root: scrollContainer, rootMargin: `0px 0px ${PINNED_TOLERANCE_PX}px 0px` }
    );
    intersectionObserver.observe(restingBottom);

    const resizeObserver = new ResizeObserver(applyScrollPadding);
    if (scrollContainer) resizeObserver.observe(scrollContainer);

    return () => {
      intersectionObserver.disconnect();
      resizeObserver.disconnect();
    };
  }, []);

  return (
    <>
      <Row
        ref={actionsRef}
        data-form-actions
        data-pinned={isPinned || undefined}
        className={classNames(
          "sticky -bottom-(--form-actions-scroll-padding)",
          "-mt-3.25 mb-0 justify-end border-transparent border-t border-b-0 py-3",
          "data-pinned:border-border-strong data-pinned:bg-table-cell-pinned",
          className
        )}
        {...props}
      />
      <div ref={restingBottomRef} aria-hidden />
    </>
  );
};

interface FormSubmitProps extends Omit<ButtonProps, "type" | "slot"> {}

export const FormSubmit = ({ ...props }: FormSubmitProps) => {
  const { formState } = useFormContext();

  const isLoading = formState.isSubmitting || formState.isValidating;

  return <Button isPending={isLoading} {...props} type="submit" />;
};
