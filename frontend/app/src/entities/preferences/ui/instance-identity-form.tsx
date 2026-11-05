import React from "react";
import { useForm, useFormState, useWatch } from "react-hook-form";
import { toast } from "react-toastify";

import { Row } from "@/shared/components/container";
import { DetailRow } from "@/shared/components/display/detail-row";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { Combobox, type ComboboxItem } from "@/shared/components/inputs/combobox";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormField, FormInput, FormMessage, FormSubmit } from "@/shared/components/ui/form";
import { Input } from "@/shared/components/ui/input";

import {
  INSTANCE_COLORS,
  INSTANCE_LABEL_MAX_LENGTH,
  type InstanceColor,
} from "@/entities/preferences/domain/model/instance-identity";
import {
  INSTANCE_COLOR_LABELS,
  instanceBarClassName,
} from "@/entities/preferences/domain/rules/instance-color";
import {
  instanceLabelError,
  normalizeInstanceLabel,
} from "@/entities/preferences/domain/rules/validate-instance-label";
import { toFieldValue } from "@/entities/preferences/ui/preference-fields";
import { useGlobalPreferences } from "@/entities/preferences/ui/queries/get-global-preferences.query";
import { useUpdateGlobalPreferences } from "@/entities/preferences/ui/queries/update-global-preferences.mutation";

const INSTANCE_COLOR_ITEMS: Array<ComboboxItem> = INSTANCE_COLORS.map((color) => ({
  value: color,
  label: INSTANCE_COLOR_LABELS[color],
  icon: <span aria-hidden className={`size-3 rounded-full ${instanceBarClassName(color)}`} />,
}));

function labelText(fieldValue: FormAttributeValue | undefined): string {
  return typeof fieldValue?.value === "string" ? fieldValue.value : "";
}

function InstanceLabelField() {
  const countId = React.useId();
  const fieldValue = useWatch({ name: "instance_label" }) as FormAttributeValue | undefined;
  const count = labelText(fieldValue).length;

  return (
    <DetailRow icon="mdi:tag-text-outline" label="Instance label">
      <FormField
        name="instance_label"
        defaultValue={DEFAULT_FORM_FIELD_VALUE}
        rules={{
          validate: (value: FormAttributeValue) => instanceLabelError(labelText(value)) ?? true,
        }}
        render={({ field }) => (
          <div className="w-64 shrink-0">
            <FormInput>
              <Input
                {...field}
                aria-label="Instance label"
                aria-describedby={countId}
                value={labelText(field.value)}
                onChange={(event) => field.onChange(toFieldValue(event.target.value))}
              />
            </FormInput>
            <p id={countId} className="mt-1 text-foreground-muted text-xs">
              {count}/{INSTANCE_LABEL_MAX_LENGTH}
            </p>
            <FormMessage className="mt-1" />
          </div>
        )}
      />
    </DetailRow>
  );
}

function InstanceColorField() {
  return (
    <DetailRow icon="mdi:palette-outline" label="Instance color">
      <div className="w-64 shrink-0">
        <FormField
          name="instance_color"
          defaultValue={DEFAULT_FORM_FIELD_VALUE}
          render={({ field }) => (
            <Combobox
              value={(field.value?.value as string | null) ?? null}
              onChange={(newValue) => field.onChange(toFieldValue(newValue))}
              items={INSTANCE_COLOR_ITEMS}
              label="Instance color"
              placeholder="No color"
              emptyMessage="No color found."
            />
          )}
        />
      </div>
    </DetailRow>
  );
}

function SaveButton({ isPending }: { isPending?: boolean }) {
  const { isDirty, isValid } = useFormState();

  return (
    <FormSubmit isPending={isPending} isDisabled={!isDirty || !isValid}>
      Save instance identity
    </FormSubmit>
  );
}

export function InstanceIdentityForm() {
  const { isPending, error, data: global } = useGlobalPreferences();
  const updatePreferences = useUpdateGlobalPreferences();

  if (isPending) {
    return <LoadingIndicator className="h-32" />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the global preferences" />;
  }

  return (
    <InstanceIdentityFormContent
      defaultValues={{
        instance_label: toFieldValue(global.instanceLabel),
        instance_color: toFieldValue(global.instanceColor),
      }}
      isPending={updatePreferences.isPending}
      onSubmit={(formData) => {
        updatePreferences.mutate(
          {
            instanceLabel: normalizeInstanceLabel(labelText(formData.instance_label)),
            instanceColor: (formData.instance_color?.value as InstanceColor | null) ?? null,
          },
          {
            onSuccess: () => {
              toast(<Alert type={ALERT_TYPES.SUCCESS} message="Instance identity updated" />);
            },
            onError: (mutationError) => {
              toast(
                <Alert
                  type={ALERT_TYPES.ERROR}
                  message={
                    mutationError instanceof Error
                      ? mutationError.message
                      : "Failed to update the instance identity"
                  }
                />
              );
            },
          }
        );
      }}
    />
  );
}

interface InstanceIdentityFormValues {
  instance_label: FormAttributeValue;
  instance_color: FormAttributeValue;
}

function InstanceIdentityFormContent({
  defaultValues,
  isPending,
  onSubmit,
}: {
  defaultValues: InstanceIdentityFormValues;
  isPending: boolean;
  onSubmit: (values: InstanceIdentityFormValues) => void;
}) {
  // Validating on change surfaces the length rule while the admin types instead of after a submit.
  const form = useForm<InstanceIdentityFormValues>({ defaultValues, mode: "onChange" });

  return (
    <Form form={form} onSubmit={onSubmit} className="space-y-0 divide-y">
      <InstanceLabelField />
      <InstanceColorField />

      <Row className="justify-end p-2">
        <SaveButton isPending={isPending} />
      </Row>
    </Form>
  );
}
