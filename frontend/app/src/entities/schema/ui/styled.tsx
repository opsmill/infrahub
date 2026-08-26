import type { ReactElement } from "react";
import { Tab, TabPanel, type TabPanelProps, type TabProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import Accordion, { type AccordionProps } from "@/shared/components/display/accordion";
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

        {description && <p className="font-normal text-foreground-muted text-xs">{description}</p>}
      </h4>
    }
    className="rounded-sm bg-card p-3 shadow-card"
    {...props}
  >
    <article className="mt-3 divide-y rounded-sm bg-panel px-2 shadow-panel">{children}</article>
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
        "px-4 py-2 text-sm hover:bg-highlight focus:bg-highlight focus:outline-hidden",
        isSelected ? "border-b-2 border-b-accent font-semibold" : "cursor-pointer",
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
        "min-h-0 grow space-y-2 overflow-auto bg-background p-2 outline-hidden",
        focusVisibleStyle,
        className
      )}
      {...props}
    />
  );
};

export const NullDisplay = () => <div className="text-subtle-muted text-xs">null</div>;

export const SchemaKindDisplay = ({
  kinds,
  onKindClick,
}: {
  kinds?: string[];
  onKindClick?: (kind: string) => void;
}) => {
  if (!kinds) return null;
  if (kinds.length === 0) return <span>empty</span>;

  return (
    <div className="flex flex-col items-end space-y-1">
      {kinds.map((kind) => (
        <Badge
          key={kind}
          className={classNames(
            "border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-400/30 dark:bg-sky-400/20 dark:text-sky-300",
            onKindClick && "cursor-pointer hover:bg-sky-100 dark:hover:bg-sky-400/30"
          )}
          onClick={onKindClick ? () => onKindClick(kind) : undefined}
        >
          {kind}
        </Badge>
      ))}
    </div>
  );
};
