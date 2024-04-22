import React from "react";
import { classNames } from "../../utils/common";

export type Property = {
  name: string;
  value?: React.ReactNode;
};

export interface PropertyListProps extends React.HTMLAttributes<HTMLTableElement> {
  properties: Array<Property>;
  bodyClassName?: string;
  cellClassName?: string;
}

export interface PropertyRowProps extends React.HTMLAttributes<HTMLTableCellElement> {
  data: Property;
}

export const PropertyRow = ({ data, className, ...props }: PropertyRowProps) => {
  return (
    <tr>
      <td className={classNames("p-2 text-gray-600", className)} {...props}>
        {data.name}
      </td>
      <td className={classNames("p-2", className)} {...props}>
        {data.value ?? "-"}
      </td>
    </tr>
  );
};

export const PropertyList = ({
  properties,
  className,
  bodyClassName,
  cellClassName,
  ...props
}: PropertyListProps) => {
  return (
    <table
      className={classNames("table-auto border-spacing-2 border-collapse text-sm", className)}
      {...props}>
      <tbody className={classNames("divide-y", bodyClassName)}>
        {properties.map((property) => {
          return <PropertyRow key={property.name} data={property} className={cellClassName} />;
        })}
      </tbody>
    </table>
  );
};
