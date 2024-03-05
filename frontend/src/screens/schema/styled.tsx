import Accordion, { AccordionProps } from "../../components/display/accordion";
import { Badge } from "../../components/ui/badge";
import { ReactElement } from "react";
import { Tab } from "@headlessui/react";
import { classNames, warnUnexpectedType } from "../../utils/common";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../../config/qsp";

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
    className="bg-custom-white shadow p-3 rounded"
    {...props}>
    <article className="divide-y px-2 mt-3 bg-gray-100 rounded">{children}</article>
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
    if (value === null) return <NullDisplay />;

    switch (typeof value) {
      case "string":
      case "number":
        return value;
      case "boolean":
        return (
          <div
            className={classNames(
              "text-xs border-2 rounded px-2 py-0.5 font-semibold",
              value ? "text-green-700 border-green-500" : "text-red-700 border-red-500"
            )}>
            {value.toString()}
          </div>
        );
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
    <dl className="flex justify-between items-start gap-4 text-sm p-2 py-3">
      <dt>{title}</dt>
      <dd className="flex-grow shrink font-medium text-end flex justify-end">{formatValue()}</dd>
    </dl>
  );
};

export const TabStyled = ({ children }: { children: ReactElement | string }) => (
  <Tab
    className={({ selected }) =>
      classNames(
        "px-4 py-2 text-sm hover:bg-gray-100 focus:outline-none focus:bg-gray-100",
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

export const NullDisplay = () => (
  <div className="text-xs border-2 rounded px-2 py-0.5 text-gray-500 border-gray-300">null</div>
);

export const ModelDisplay = ({ kinds }: { kinds?: string[] }) => {
  const [, setKind] = useQueryParam(QSP.KIND, StringParam);
  if (!kinds) return null;
  if (kinds.length === 0) return "empty";

  return (
    <div className="space-y-1 flex flex-col items-end">
      {kinds.map((kind) => (
        <Badge
          key={kind}
          className="bg-sky-50 text-sky-800 border-sky-200 hover:bg-sky-100 cursor-pointer"
          onClick={() => setKind(kind)}>
          {kind}
        </Badge>
      ))}
    </div>
  );
};
