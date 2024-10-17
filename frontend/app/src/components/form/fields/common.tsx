import { QuestionMark } from "@/components/display/question-mark";
import {
  AttributeValueFromProfile,
  FormFieldValue,
  RelationshipValueFormPool,
} from "@/components/form/type";
import { Badge } from "@/components/ui/badge";
import { FormLabel } from "@/components/ui/form";
import { LabelProps } from "@/components/ui/label";
import { Tooltip } from "@/components/ui/tooltip";
import { classNames } from "@/utils/common";
import { getObjectDetailsUrl2 } from "@/utils/objects";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router-dom";

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

      {fieldData?.source?.type === "profile" && (
        <ProfileSourceBadge fieldData={fieldData as AttributeValueFromProfile} />
      )}

      {fieldData?.source?.type === "pool" && (
        <PoolSourceBadge fieldData={fieldData as RelationshipValueFormPool} />
      )}
    </div>
  );
};

const ProfileSourceBadge = ({ fieldData }: { fieldData: AttributeValueFromProfile }) => {
  return (
    <Tooltip
      enabled
      content={
        <div className="max-w-60" data-testid="source-profile-tooltip">
          <p>This value is set by a profile:</p>
          <Link
            to={getObjectDetailsUrl2(fieldData?.source.kind!, fieldData?.source.id)}
            className="underline inline-flex items-center gap-1"
          >
            {fieldData?.source?.label} <Icon icon="mdi:open-in-new" />
          </Link>
          <p className="text-xs mt-2">You can override it by typing another value in the input.</p>
        </div>
      }
    >
      <button type="button" className="ml-auto" data-testid="source-profile-badge">
        <Badge variant="green">
          <Icon icon="mdi:shape-plus-outline" className="mr-1" /> {fieldData?.source?.label}
        </Badge>
      </button>
    </Tooltip>
  );
};

const PoolSourceBadge = ({ fieldData }: { fieldData: RelationshipValueFormPool }) => {
  return (
    <Tooltip
      enabled
      content={
        <div className="max-w-60">
          <p>This value is allocated from the pool:</p>
          <Link
            to={getObjectDetailsUrl2(fieldData?.source.kind!, fieldData?.source.id)}
            className="underline inline-flex items-center gap-1"
          >
            {fieldData?.source?.label} <Icon icon="mdi:open-in-new" />
          </Link>
          <p className="text-xs mt-2">You can override it by entering another value manually.</p>
        </div>
      }
    >
      <button type="button" className="ml-auto" data-testid="source-pool-badge">
        <Badge variant="purple">
          <Icon icon="mdi:view-grid-outline" className="mr-1" /> {fieldData?.source?.label}
        </Badge>
      </button>
    </Tooltip>
  );
};
