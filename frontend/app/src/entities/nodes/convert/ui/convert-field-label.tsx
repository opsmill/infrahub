import { Row } from "@/shared/components/container";
import { QuestionMark } from "@/shared/components/display/question-mark";
import { InputUniqueTips } from "@/shared/components/form/fields/common";
import { Badge } from "@/shared/components/ui/badge";
import { FormLabel } from "@/shared/components/ui/form";
import type { LabelProps } from "@/shared/components/ui/label";
import { classNames } from "@/shared/utils/common";

interface ConvertFieldLabelProps extends Omit<LabelProps, "onChange"> {
  label?: string;
  required?: boolean;
  unique?: boolean;
  description?: string | null;
  kind: string;
}

export const ConvertFieldLabel = ({
  className,
  label,
  required,
  unique,
  description,
  variant,
  kind,
}: ConvertFieldLabelProps) => {
  return (
    <Row className={classNames("h-4", className)}>
      <FormLabel variant={variant}>
        {label} {required && "*"}
      </FormLabel>
      {kind && <Badge variant="lightgray-outline">{kind}</Badge>}
      {unique && <InputUniqueTips className="self-end pb-0.5" />}
      {description && <QuestionMark message={description} />}
    </Row>
  );
};
