import Accordion, { AccordionProps } from "../../components/display/accordion";
import { Badge } from "../../components/ui/badge";
import { ReactElement } from "react";
import { components } from "../../infraops";
import { Tab } from "@headlessui/react";
import { classNames } from "../../utils/common";

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
