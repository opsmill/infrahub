import { classNames } from "@/utils/common";
import React from "react";

export type Property = {
  name: React.ReactNode;
  value?: React.ReactNode;
};

export interface PropertyListProps extends React.HTMLAttributes<HTMLTableElement> {
  properties: Array<Property>;
  bodyClassName?: string;
  labelClassName?: string;
  valueClassName?: string;
}

export interface PropertyRowProps extends React.HTMLAttributes<HTMLTableCellElement> {
  data: Property;
  labelClassName?: string;
  valueClassName?: string;
}

export const PropertyRow = ({
  data,
  labelClassName,
  valueClassName,
  ...props
}: PropertyRowProps) => {
  return (
    <tr>
      <td className={classNames("p-2 text-gray-600", labelClassName)} {...props}>
        {data.name}
      </td>
      <td className={classNames("p-2", valueClassName)} {...props}>
        {data.value ?? "-"}
      </td>
    </tr>
  );
};

export const PropertyList = ({
  properties,
  className,
  bodyClassName,
  labelClassName,
  valueClassName,
  ...props
}: PropertyListProps) => {
  return (
    <table
      className={classNames("table-auto border-spacing-2 border-collapse text-sm", className)}
      {...props}>
      <tbody className={classNames("divide-y", bodyClassName)}>
        {properties.map((property, index) => {
          return (
            <PropertyRow
              key={index}
              data={property}
              labelClassName={labelClassName}
              valueClassName={valueClassName}
            />
          );
        })}
      </tbody>
    </table>
  );
};
