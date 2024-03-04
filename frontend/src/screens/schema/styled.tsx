import Accordion, { AccordionProps } from "../../components/display/accordion";
import { Badge } from "../../components/ui/badge";
import { ReactElement } from "react";
import { Tab } from "@headlessui/react";
import { classNames, warnUnexpectedType } from "../../utils/common";
import { Icon } from "@iconify-icon/react";

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
  value: string | string[] | number | boolean | ReactElement | null | undefined;
}) => {
  if (value === undefined) return null;

  const formatValue = () => {
    if (value === null || value === undefined) return "-";

    switch (typeof value) {
      case "string":
      case "number":
        return value;
      case "boolean":
        return <Icon icon={value ? "mdi:check" : "mdi:remove"} />;
      case "object":
        if (Array.isArray(value))
          return (
            <ul>
              {value.map((v) => (
                <li key={v}>{v}</li>
              ))}
            </ul>
          );
        return value;
      default:
        warnUnexpectedType(value);
        return value;
    }
  };

  return (
    <dl className="flex justify-between items-baseline gap-4 text-sm p-2">
      <dt>{title}</dt>
      <dd className="flex-grow shrink font-medium text-end">{formatValue()}</dd>
    </dl>
  );
};

export const TabStyled = ({ children }: { children: ReactElement | string }) => (
  <Tab
    className={({ selected }) =>
      classNames(
        "px-4 py-1 text-sm hover:bg-gray-100 focus:outline-none focus:bg-gray-100",
        selected ? "border-b-2 border-b-custom-blue-600 font-semibold" : ""
      )
    }>
    {children}
  </Tab>
);

export const TabPanelStyled = ({
  children,
}: {
  children?: ReactElement | ReactElement[] | string;
}) => {
  return <Tab.Panel className="space-y-2">{children}</Tab.Panel>;
};
