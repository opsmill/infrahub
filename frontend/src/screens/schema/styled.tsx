import Accordion, { AccordionProps } from "../../components/display/accordion";
import { Badge } from "../../components/ui/badge";
import { ReactElement } from "react";
import { components } from "../../infraops";

interface AccordionStyleProps extends AccordionProps {
  title: ReactElement | string;
  kind: ReactElement | string;
  description?: string | null;
  isOptional?: boolean;
  isUnique?: boolean;
  isReadOnly?: boolean;
}

export const AccordionStyled = ({
  children,
  title,
  kind,
  description,
  isOptional,
  isUnique,
  isReadOnly,
  ...props
}: AccordionStyleProps) => (
  <Accordion
    title={
      <h4>
        <div className="flex items-center justify-between gap-2">
          <div className="text-sm shrink-0">
            {title} {kind && <Badge>{kind}</Badge>}
          </div>

          <div className="space-x-1">
            {isOptional && <Badge variant="yellow">optional</Badge>}
            {isUnique && <Badge variant="red">unique</Badge>}
            {isReadOnly && <Badge variant="blue">read-only</Badge>}
          </div>
        </div>

        {description && <p className="text-xs text-gray-600 font-normal">{description}</p>}
      </h4>
    }
    className="bg-custom-white shadow p-2 rounded"
    {...props}>
    <article className="divide-y px-2 mt-2 bg-gray-100">{children}</article>
  </Accordion>
);
export const PropertyRow = ({
  title,
  value,
}: {
  title: string;
  value:
    | string
    | string[]
    | string[][]
    | components["schemas"]["DropdownChoice"][]
    | number
    | boolean
    | ReactElement
    | null
    | undefined;
}) => {
  if (value === undefined) return null;

  return (
    <dl className="text-gray-500 flex justify-between items-baseline text-sm p-2">
      <dt>{title}</dt>
      <dd className="truncate">{value || "-"}</dd>
    </dl>
  );
};
