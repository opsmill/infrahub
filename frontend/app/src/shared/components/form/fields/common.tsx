import { Icon } from "@iconify-icon/react";
import { FileBoxIcon } from "lucide-react";
import type { ControllerRenderProps } from "react-hook-form";
import { Link } from "react-router";

import { QuestionMark } from "@/shared/components/display/question-mark";
import type {
  FormAttributeValue,
  FormFieldValue,
  FormRelationshipValue,
  PoolSource,
  ProfileSource,
  TemplateSource,
} from "@/shared/components/form/type";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { Checkbox } from "@/shared/components/inputs/checkbox";
import { Badge } from "@/shared/components/ui/badge";
import { FormLabel } from "@/shared/components/ui/form";
import type { LabelProps } from "@/shared/components/ui/label";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";

export const InputUniqueTips = ({ className }: { className: string }) => (
  <span className={classNames("text-gray-600 text-xs italic leading-3", className)}>
    must be unique
  </span>
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
  fieldData,
  ...props
}: LabelFormFieldProps) => {
  return (
    <div className={classNames("flex h-4 items-center gap-1", className)}>
      <FormLabel {...props}>
        {label} {required && "*"}
      </FormLabel>
      {unique && <InputUniqueTips className="mb-px self-end" />}
      {description && <QuestionMark message={description} className="ml-1" />}

      {fieldData?.source?.type === "profile" && <ProfileSourceBadge source={fieldData.source} />}
      {fieldData?.source?.type === "pool" && <PoolSourceBadge source={fieldData.source} />}
      {fieldData?.source?.type === "template" && <TemplateSourceBadge source={fieldData.source} />}
    </div>
  );
};

const ProfileSourceBadge = ({ source }: { source: ProfileSource }) => {
  return (
    <Tooltip
      enabled
      content={
        <div className="max-w-60" data-testid="source-profile-tooltip">
          <p>This value is set by a profile:</p>
          <Link
            to={getObjectDetailsUrl(source.kind!, source.id)}
            className="inline-flex items-center gap-1 underline"
          >
            {source?.label} <Icon icon="mdi:open-in-new" />
          </Link>
          <p className="mt-2 text-xs">You can override it by typing another value in the input.</p>
        </div>
      }
    >
      <button type="button" className="ml-auto" data-testid="source-profile-badge">
        <Badge variant="green">
          <Icon icon="mdi:shape-plus-outline" className="mr-1" /> {source?.label}
        </Badge>
      </button>
    </Tooltip>
  );
};

const PoolSourceBadge = ({ source }: { source: PoolSource }) => {
  return (
    <Tooltip
      enabled
      content={
        <div className="max-w-60">
          <p>This value is allocated from the pool:</p>
          <Link
            to={getObjectDetailsUrl(source.kind!, source.id)}
            className="inline-flex items-center gap-1 underline"
          >
            {source?.label} <Icon icon="mdi:open-in-new" />
          </Link>
          <p className="mt-2 text-xs">You can override it by entering another value manually.</p>
        </div>
      }
    >
      <button type="button" className="ml-auto" data-testid="source-pool-badge">
        <Badge variant="purple">
          <Icon icon="mdi:view-grid-outline" className="mr-1" /> {source?.label}
        </Badge>
      </button>
    </Tooltip>
  );
};

const TemplateSourceBadge = ({ source }: { source: TemplateSource }) => {
  return (
    <Tooltip
      enabled
      content={
        <div className="max-w-60">
          <p>This value is from the following template:</p>
          <Link
            to={getObjectDetailsUrl(source.kind!, source.id)}
            className="inline-flex items-center gap-1 underline"
          >
            {source?.label} <Icon icon="mdi:open-in-new" />
          </Link>
          <p className="mt-2 text-xs">You can override it by entering another value manually.</p>
        </div>
      }
    >
      <button type="button" className="ml-auto" data-testid="source-template-badge">
        <Badge variant="blue">
          <FileBoxIcon className="mr-1 size-3" /> {source?.label}
        </Badge>
      </button>
    </Tooltip>
  );
};

interface ResetActionProps {
  field: ControllerRenderProps;
  defaultValue: FormAttributeValue | FormRelationshipValue;
}

export const ResetAction = ({ field, defaultValue }: ResetActionProps) => {
  return (
    <div className="flex justify-end gap-2 text-gray-600 text-xs">
      <label htmlFor={`reset_${field.name}`} className="flex cursor-pointer items-center gap-2">
        <Checkbox
          id={`reset_${field.name}`}
          value={field.value?.source?.type === "user" && field.value?.value === null}
          onClick={(event) => {
            const value = event.target.checked;

            if (value) {
              return field.onChange(updateFormFieldValue(null));
            }
            return field.onChange(defaultValue);
          }}
        />
        Set empty
      </label>

      {/* //TODO: Switch to aria component after fixing issue with scroll after checking the input
          //TODO: Example available with Role and Remove Tags fields on Device */}
      {/* <Checkbox
        onChange={(value) => {
          if (value) {
            return field.onChange(updateFormFieldValue(null));
          }
          return field.onChange(defaultValue);
        }}
      >
        Set empty
      </Checkbox> */}
    </div>
  );
};
