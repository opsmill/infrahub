import { parseAsNativeArrayOf, parseAsString, useQueryState } from "nuqs";
import type { ReactElement } from "react";
import { Tab, TabPanel, type TabPanelProps, type TabProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import Accordion, { type AccordionProps } from "@/shared/components/display/accordion";
import { Badge } from "@/shared/components/ui/badge";
import { QSP } from "@/shared/config/qsp";
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
          <div className="grow text-sm">
            {title} {kind && <Badge>{kind}</Badge>}
          </div>

          <div className="space-x-1">
            {isOptional && <Badge variant="yellow">optional</Badge>}
            {isUnique && <Badge variant="red">unique</Badge>}
            {isReadOnly && <Badge variant="blue">read-only</Badge>}
            {isComputed && <Badge variant="green">computed</Badge>}
          </div>
        </div>

        {description && <p className="font-normal text-gray-600 text-xs">{description}</p>}
      </h4>
    }
    className="rounded-sm bg-white p-3 shadow-sm"
    {...props}
  >
    <article className="mt-3 divide-y divide-gray-200 rounded-sm bg-gray-100 px-2">
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
        return <Badge variant={value ? "green" : "red"}>{value.toString()}</Badge>;
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
    <dl className="flex items-start justify-between gap-4 p-2 py-3 text-sm">
      <dt>{title}</dt>
      <dd className="flex shrink grow justify-end text-end font-medium">{formatValue()}</dd>
    </dl>
  );
};

export const PropertyTitle = ({ title }: { title: string }) => {
  return (
    <dl className="flex items-start justify-between gap-4 p-2 py-3 font-semibold text-sm">
      <dt>{title}</dt>
    </dl>
  );
};

export const TabStyled = ({ className, ...props }: TabProps) => (
  <Tab
    className={({ isSelected }) =>
      classNames(
        "px-4 py-2 text-sm hover:bg-gray-100 focus:bg-gray-100 focus:outline-hidden",
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
        "min-h-0 grow space-y-2 overflow-auto bg-gray-100 p-2 outline-hidden",
        focusVisibleStyle,
        className
      )}
      {...props}
    />
  );
};

export const NullDisplay = () => <div className="text-gray-500 text-xs">null</div>;

export const ModelDisplay = ({ kinds }: { kinds?: string[] }) => {
  const [selectedKinds, setKinds] = useQueryState(QSP.KIND, parseAsNativeArrayOf(parseAsString));
  if (!kinds) return null;
  if (kinds.length === 0) return <span>empty</span>;

  return (
    <div className="flex flex-col items-end space-y-1">
      {kinds.map((kind) => (
        <Badge
          key={kind}
          className="cursor-pointer border-sky-200 bg-sky-50 text-sky-800 hover:bg-sky-100"
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
    <div className="flex flex-col items-end space-y-1">
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
