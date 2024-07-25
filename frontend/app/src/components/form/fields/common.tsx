import { FormLabel } from "@/components/ui/form";
import { QuestionMark } from "@/components/display/question-mark";
import { classNames } from "@/utils/common";
import { LabelProps } from "@/components/ui/label";
import { Icon } from "@iconify-icon/react";
import { Badge } from "@/components/ui/badge";
import React from "react";
import { FormFieldValue } from "@/components/form/type";
import { Tooltip } from "@/components/ui/tooltip";
import { Link } from "react-router-dom";
import { getObjectDetailsUrl2 } from "@/utils/objects";

export const InputUniqueTips = () => (
  <span className="text-xs text-gray-600 italic self-end mb-px">must be unique</span>
);

interface LabelFormFieldProps extends LabelProps {
  className?: string;
  label?: string;
  required?: boolean;
  unique?: boolean;
  description?: string | null;
  fieldData?: FormFieldValue;
}

export const LabelFormField = ({
  className,
  label,
  required,
  unique,
  description,
  variant,
  fieldData,
}: LabelFormFieldProps) => {
  return (
    <div className={classNames("h-5 mb-1 flex items-center gap-1", className)}>
      <FormLabel variant={variant}>
        {label} {required && "*"}
      </FormLabel>
      {unique && <InputUniqueTips />}
      {description && <QuestionMark message={description} />}

      {fieldData?.source?.type === "profile" && (
        <Tooltip
          enabled
          content={
            <div className="max-w-60">
              <p>This value is set by a profile:</p>
              <Link
                to={getObjectDetailsUrl2(fieldData?.source.kind!, fieldData?.source.id)}
                className="underline inline-flex items-center gap-1">
                {fieldData?.source?.label} <Icon icon="mdi:open-in-new" />
              </Link>
              <p className="text-xs mt-2">
                You can override it by typing another value in the input.
              </p>
            </div>
          }>
          <button className="ml-auto">
            <Badge variant="green">
              <Icon icon="mdi:shape-plus-outline" className="mr-1" /> {fieldData?.source?.label}
            </Badge>
          </button>
        </Tooltip>
      )}

      {fieldData?.source?.type === "pool" && (
        <Tooltip
          enabled
          content={
            <div className="max-w-60">
              <p>This value is allocated from the pool:</p>
              <Link
                to={getObjectDetailsUrl2(fieldData?.source.kind!, fieldData?.source.id)}
                className="underline inline-flex items-center gap-1">
                {fieldData?.source?.label} <Icon icon="mdi:open-in-new" />
              </Link>
              <p className="text-xs mt-2">
                You can override it by entering another value manually.
              </p>
            </div>
          }>
          <button className="ml-auto">
            <Badge variant="purple">
              <Icon icon="mdi:view-grid-outline" className="mr-1" /> {fieldData?.source?.label}
            </Badge>
          </button>
        </Tooltip>
      )}
    </div>
  );
};
