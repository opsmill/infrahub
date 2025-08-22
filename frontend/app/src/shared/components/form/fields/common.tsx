import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { QuestionMark } from "@/shared/components/display/question-mark";
import {
  FormAttributeValue,
  FormFieldValue,
  FormRelationshipValue,
  PoolSource,
  ProfileSource,
  TemplateSource,
} from "@/shared/components/form/type";
import { Badge } from "@/shared/components/ui/badge";
import { FormLabel } from "@/shared/components/ui/form";
import { LabelProps } from "@/shared/components/ui/label";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { FileBoxIcon } from "lucide-react";
import { ControllerRenderProps } from "react-hook-form";
import { Link } from "react-router";
import { Checkbox } from "../../aria/checkbox";
import { updateFormFieldValue } from "../utils/updateFormFieldValue";

export const InputUniqueTips = ({ className }: { className: string }) => (
  <span className={classNames("text-xs leading-3 text-gray-600 italic", className)}>
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
  variant,
  fieldData,
}: LabelFormFieldProps) => {
  return (
    <div className={classNames("h-4 flex items-center gap-1", className)}>
      <FormLabel variant={variant}>
        {label} {required && "*"}
      </FormLabel>
      {unique && <InputUniqueTips className="self-end mb-px" />}
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
            className="underline inline-flex items-center gap-1"
          >
            {source?.label} <Icon icon="mdi:open-in-new" />
          </Link>
          <p className="text-xs mt-2">You can override it by typing another value in the input.</p>
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
            className="underline inline-flex items-center gap-1"
          >
            {source?.label} <Icon icon="mdi:open-in-new" />
          </Link>
          <p className="text-xs mt-2">You can override it by entering another value manually.</p>
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
            className="underline inline-flex items-center gap-1"
          >
            {source?.label} <Icon icon="mdi:open-in-new" />
          </Link>
          <p className="text-xs mt-2">You can override it by entering another value manually.</p>
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
    <div className="text-xs text-gray-600 flex justify-end gap-2">
      <Checkbox
        isSelected={field.value?.source?.type === "user" && field.value?.value === null}
        onChange={(value) => {
          if (value) {
            return field.onChange(updateFormFieldValue(null));
          }
          return field.onChange(defaultValue);
        }}
      >
        Set empty
      </Checkbox>
    </div>
  );
};
