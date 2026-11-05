import React from "react";
import { type FieldNamesMarkedBoolean, useForm, useFormState, useWatch } from "react-hook-form";
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
import { classNames } from "@/shared/utils/common";

import {
  INSTANCE_COLORS,
  INSTANCE_LABEL_MAX_LENGTH,
  type InstanceColor,
  isInstanceColor,
} from "@/entities/preferences/domain/model/instance-identity";
import {
  instanceBarClassName,
  instanceColorLabel,
} from "@/entities/preferences/domain/rules/instance-color";
import {
  instanceLabelError,
  instanceLabelLength,
  normalizeInstanceLabel,
} from "@/entities/preferences/domain/rules/validate-instance-label";
import type { UpdateGlobalPreferenceParams } from "@/entities/preferences/domain/use-cases/update-global-preference";
import { toFieldValue } from "@/entities/preferences/ui/preference-fields";
import { useGlobalPreferences } from "@/entities/preferences/ui/queries/get-global-preferences.query";
import { useUpdateGlobalPreferences } from "@/entities/preferences/ui/queries/update-global-preferences.mutation";

interface InstanceIdentityFormValues {
  instance_label: FormAttributeValue;
  instance_color: FormAttributeValue;
}

const INSTANCE_COLOR_ITEMS: Array<ComboboxItem> = INSTANCE_COLORS.map((color) => ({
  value: color,
  label: instanceColorLabel(color),
  icon: (
    <span
      aria-hidden
      className={classNames("size-3 shrink-0 rounded-full", instanceBarClassName(color))}
    />
  ),
}));

function labelText(fieldValue: FormAttributeValue): string {
  return typeof fieldValue.value === "string" ? fieldValue.value : "";
}

function colorValue(fieldValue: FormAttributeValue): InstanceColor | null {
  return isInstanceColor(fieldValue.value) ? fieldValue.value : null;
}

/** Only the fields the admin changed are sent, so a save does not overwrite another admin's save of the other field. */
function changedFields(
  values: InstanceIdentityFormValues,
  dirtyFields: Partial<FieldNamesMarkedBoolean<InstanceIdentityFormValues>>
): UpdateGlobalPreferenceParams {
  const params: UpdateGlobalPreferenceParams = {};
  if (dirtyFields.instance_label) {
    params.instanceLabel = normalizeInstanceLabel(labelText(values.instance_label));
  }
  if (dirtyFields.instance_color) {
    params.instanceColor = colorValue(values.instance_color);
  }
  return params;
}

function InstanceLabelField() {
  const countId = React.useId();
  const fieldValue = useWatch<InstanceIdentityFormValues, "instance_label">({
    name: "instance_label",
  });
  const count = instanceLabelLength(labelText(fieldValue));

  return (
    <DetailRow icon="mdi:tag-text-outline" label="Instance label">
      <FormField
        name="instance_label"
        defaultValue={DEFAULT_FORM_FIELD_VALUE}
        rules={{
          validate: (value: FormAttributeValue) => instanceLabelError(labelText(value)) ?? true,
        }}
        render={({ field }) => {
          const fieldData: FormAttributeValue = field.value;

          return (
            <div className="w-64 shrink-0">
              <FormInput>
                <Input
                  {...field}
                  aria-label="Instance label"
                  aria-describedby={countId}
                  value={labelText(fieldData)}
                  onChange={(event) => field.onChange(toFieldValue(event.target.value))}
                />
              </FormInput>
              <p id={countId} className="mt-1 text-foreground-muted text-xs tabular-nums">
                {count}/{INSTANCE_LABEL_MAX_LENGTH}
              </p>
              <FormMessage className="mt-1" />
            </div>
          );
        }}
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
          render={({ field }) => {
            const fieldData: FormAttributeValue = field.value;

            return (
              <Combobox
                value={colorValue(fieldData)}
                onChange={(newValue) => field.onChange(toFieldValue(newValue))}
                items={INSTANCE_COLOR_ITEMS}
                label="Instance color"
                placeholder="No color"
                emptyMessage="No color found."
              />
            );
          }}
        />
      </div>
    </DetailRow>
  );
}

function SaveButton({ isPending }: { isPending?: boolean }) {
  const { isDirty } = useFormState();

  return (
    <FormSubmit isPending={isPending} isDisabled={!isDirty}>
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
      onSave={(params) => {
        updatePreferences.mutate(params, {
          onSuccess: () => {
            toast(<Alert type={ALERT_TYPES.SUCCESS} message="Instance identity updated" />);
          },
          onError: (mutationError) => {
            toast(<Alert type={ALERT_TYPES.ERROR} message={mutationError.message} />);
          },
        });
      }}
    />
  );
}

function InstanceIdentityFormContent({
  defaultValues,
  isPending,
  onSave,
}: {
  defaultValues: InstanceIdentityFormValues;
  isPending: boolean;
  onSave: (params: UpdateGlobalPreferenceParams) => void;
}) {
  // Validate on change so the length rule shows while the admin types.
  const form = useForm<InstanceIdentityFormValues>({ defaultValues, mode: "onChange" });
  const { dirtyFields } = useFormState({ control: form.control });

  return (
    <Form
      form={form}
      onSubmit={(values) => onSave(changedFields(values, dirtyFields))}
      className="space-y-0 divide-y"
    >
      <InstanceLabelField />
      <InstanceColorField />

      <Row className="justify-end p-2">
        <SaveButton isPending={isPending} />
      </Row>
    </Form>
  );
}
