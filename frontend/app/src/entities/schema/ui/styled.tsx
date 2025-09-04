import { ReactElement } from "react";
import { Tab, TabPanel, TabPanelProps, TabProps } from "react-aria-components";
import { ArrayParam, useQueryParam } from "use-query-params";

import { QSP } from "@/config/qsp";

import Accordion, { AccordionProps } from "@/shared/components/display/accordion";
import { focusVisibleStyle } from "@/shared/components/style-rac";
import { Badge } from "@/shared/components/ui/badge";
import { classNames, warnUnexpectedType } from "@/shared/utils/common";

interface AccordionStyleProps extends AccordionProps {
  title: ReactElement | string;
  kind: ReactElement | string;
  description?: string | null;
  isOptional?: boolean;
  isUnique?: boolean;
  isReadOnly?: boolean;
  isComputed?: boolean;
}

export const AccordionStyled = ({
  children,
  title,
  kind,
  description,
  isOptional,
  isUnique,
  isReadOnly,
  isComputed,
  ...props
}: AccordionStyleProps) => (
  <Accordion
    title={
      <h4>
        <div className="flex items-center justify-between">
          <div className="text-sm grow">
            {title} {kind && <Badge>{kind}</Badge>}
          </div>

          <div className="space-x-1">
            {isOptional && <Badge variant="yellow">optional</Badge>}
            {isUnique && <Badge variant="red">unique</Badge>}
            {isReadOnly && <Badge variant="blue">read-only</Badge>}
            {isComputed && <Badge variant="green">computed</Badge>}
          </div>
        </div>

        {description && <p className="text-xs text-gray-600 font-normal">{description}</p>}
      </h4>
    }
    className="bg-white shadow-sm p-3 rounded-sm"
    {...props}
  >
    <article className="divide-y divide-gray-200 px-2 mt-3 bg-gray-100 rounded-sm">
      {children}
    </article>
  </Accordion>
);

export const PropertyRow = ({
  title,
  value,
}: {
  title: string;
  value: string | string[] | string[][] | number | boolean | ReactElement | null | undefined;
}) => {
  if (value === undefined) return null;

  const formatValue = () => {
    if (value === null) return <NullDisplay />;

    switch (typeof value) {
      case "string":
      case "number":
        return value;
      case "boolean":
        return <Badge variant={value ? "green-outline" : "red-outline"}>{value.toString()}</Badge>;
      case "object":
        if (Array.isArray(value)) {
          return (
            <ul>
              {value.map((v) => (
                <li key={v.toString()} className="whitespace-nowrap">
                  {Array.isArray(v) ? (
                    <Badge variant="red" className="mb-1">
                      {v.join(", ")}
                    </Badge>
                  ) : (
                    v
                  )}
                </li>
              ))}
            </ul>
          );
        }
        return value;
      default:
        warnUnexpectedType(value);
        return value;
    }
  };

  return (
    <dl className="flex justify-between items-start gap-4 text-sm p-2 py-3">
      <dt>{title}</dt>
      <dd className="grow shrink font-medium text-end flex justify-end">{formatValue()}</dd>
    </dl>
  );
};

export const PropertyTitle = ({ title }: { title: string }) => {
  return (
    <dl className="flex justify-between items-start gap-4 text-sm font-semibold p-2 py-3">
      <dt>{title}</dt>
    </dl>
  );
};

export const TabStyled = ({ className, ...props }: TabProps) => (
  <Tab
    className={({ isSelected }) =>
      classNames(
        "px-4 py-2 text-sm hover:bg-gray-100 focus:outline-hidden focus:bg-gray-100",
        isSelected ? "border-b-2 border-b-custom-blue-600 font-semibold" : "cursor-pointer",
        className
      )
    }
    {...props}
  />
);

export const TabPanelStyled = ({ className, ...props }: TabPanelProps) => {
  return (
    <TabPanel
      className={classNames(
        "space-y-2 p-2 bg-gray-100 grow min-h-0 overflow-auto outline-hidden",
        focusVisibleStyle,
        className
      )}
      {...props}
    />
  );
};

export const NullDisplay = () => <div className="text-xs text-gray-500">null</div>;

export const ModelDisplay = ({ kinds }: { kinds?: string[] }) => {
  const [selectedKinds, setKinds] = useQueryParam(QSP.KIND, ArrayParam);
  if (!kinds) return null;
  if (kinds.length === 0) return <span>empty</span>;

  return (
    <div className="space-y-1 flex flex-col items-end">
      {kinds.map((kind) => (
        <Badge
          key={kind}
          className="bg-sky-50 text-sky-800 border-sky-200 hover:bg-sky-100 cursor-pointer"
          onClick={() =>
            setKinds(selectedKinds && selectedKinds?.length > 0 ? [...selectedKinds, kind] : [kind])
          }
        >
          {kind}
        </Badge>
      ))}
    </div>
  );
};

export const ListDisplay = ({ items }: { items?: string[] }) => {
  return (
    <div className="space-y-1 flex flex-col items-end">
      {items?.map((item, index) => {
        return (
          <Badge variant={"gray-outline"} key={`${item}_${index}`}>
            {item}
          </Badge>
        );
      })}
    </div>
  );
};
