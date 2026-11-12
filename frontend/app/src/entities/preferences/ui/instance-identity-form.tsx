import React from "react";
import { useWatch } from "react-hook-form";

import type { InstanceColor } from "@/shared/api/graphql/generated/types";
import { Row } from "@/shared/components/container";
import { DetailRow } from "@/shared/components/display/detail-row";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { Combobox, type ComboboxItem } from "@/shared/components/inputs/combobox";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Form, FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { Input } from "@/shared/components/ui/input";
import { classNames } from "@/shared/utils/common";

import { useConfig } from "@/entities/config/ui/config-provider";
import type { GlobalPreferences } from "@/entities/preferences/domain/model/preference";
import {
  INSTANCE_COLORS,
  instanceBarClassName,
  instanceColorLabel,
  isInstanceColor,
} from "@/entities/preferences/domain/rules/instance-color";
import {
  INSTANCE_LABEL_MAX_LENGTH,
  instanceLabelError,
  instanceLabelLength,
  normalizeInstanceLabel,
} from "@/entities/preferences/domain/rules/validate-instance-label";
import type { UpdateGlobalPreferenceParams } from "@/entities/preferences/domain/use-cases/update-global-preference";
import {
  SaveButton,
  saveWithToasts,
  toFieldValue,
} from "@/entities/preferences/ui/preference-fields";
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

/** Only the fields that differ from the saved identity are sent, so a save does not overwrite another admin's save of the other field. */
function changedFields(
  values: InstanceIdentityFormValues,
  saved: GlobalPreferences
): UpdateGlobalPreferenceParams {
  const params: UpdateGlobalPreferenceParams = {};
  const label = normalizeInstanceLabel(labelText(values.instance_label));
  if (label !== saved.instanceLabel) {
    params.instanceLabel = label;
  }
  const color = colorValue(values.instance_color);
  // The field shows a saved color this page does not know as empty, so only a picked color counts as a change.
  const savedColor = isInstanceColor(saved.instanceColor) ? saved.instanceColor : null;
  if (color !== savedColor) {
    params.instanceColor = color;
  }
  return params;
}

function InstanceLabelField({ defaultLabel }: { defaultLabel: string | null }) {
  const countId = React.useId();
  const defaultHelpId = React.useId();
  const fieldValue = useWatch<InstanceIdentityFormValues, "instance_label">({
    name: "instance_label",
  });
  const text = labelText(fieldValue);
  const count = instanceLabelLength(text);
  const showsDefaultHelp = defaultLabel !== null && normalizeInstanceLabel(text) === null;

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
                  aria-describedby={showsDefaultHelp ? `${countId} ${defaultHelpId}` : countId}
                  placeholder={defaultLabel ?? undefined}
                  value={labelText(fieldData)}
                  onChange={(event) => field.onChange(toFieldValue(event.target.value))}
                />
              </FormInput>
              <p id={countId} className="mt-1 text-foreground-muted text-xs tabular-nums">
                {count}/{INSTANCE_LABEL_MAX_LENGTH}
              </p>
              {showsDefaultHelp && (
                <p id={defaultHelpId} className="mt-1 text-foreground-muted text-xs">
                  Leave empty to use the deployment default: {defaultLabel}.
                </p>
              )}
              <FormMessage className="mt-1" />
            </div>
          );
        }}
      />
    </DetailRow>
  );
}

function InstanceColorField({ defaultColor }: { defaultColor: InstanceColor | null }) {
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
                placeholder={
                  defaultColor
                    ? `Deployment default: ${instanceColorLabel(defaultColor)}`
                    : "No color"
                }
                emptyMessage="No color found."
              />
            );
          }}
        />
      </div>
    </DetailRow>
  );
}

export function InstanceIdentityForm() {
  const { instance_defaults: instanceDefaults } = useConfig();
  const { isPending, error, data: global } = useGlobalPreferences();
  const updatePreferences = useUpdateGlobalPreferences();

  if (isPending) {
    return <LoadingIndicator className="h-32" />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the global preferences" />;
  }

  return (
    <Form<InstanceIdentityFormValues>
      mode="onChange"
      defaultValues={{
        instance_label: toFieldValue(global.instanceLabel),
        instance_color: toFieldValue(global.instanceColor),
      }}
      onSubmit={(values) =>
        saveWithToasts(() => updatePreferences.mutateAsync(changedFields(values, global)), {
          success: "Instance identity updated",
          failure: "Failed to update the instance identity",
        })
      }
      className="space-y-0 divide-y"
    >
      <InstanceLabelField defaultLabel={instanceDefaults.label} />
      <InstanceColorField
        defaultColor={isInstanceColor(instanceDefaults.color) ? instanceDefaults.color : null}
      />

      <Row className="justify-end p-2">
        <SaveButton isPending={updatePreferences.isPending}>Save instance identity</SaveButton>
      </Row>
    </Form>
  );
}
