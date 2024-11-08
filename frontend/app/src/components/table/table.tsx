import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import NoDataFound from "@/screens/errors/no-data-found";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router-dom";

import { Permission } from "@/screens/permission/types";
import { ReactNode, isValidElement } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";

export type tRowValue = {
  value: unknown;
  display: ReactNode;
};

export type tColumn = {
  name: string;
  label: string;
};

export type tRow = {
  link?: string;
  values: Record<string, string | number | tRowValue>;
};

type TableProps = {
  columns: tColumn[];
  rows: tRow[];
  constructLink?: Function;
  onDelete?: (row: tRow) => void;
  onUpdate?: (row: tRow) => void;
  className?: string;
  permission?: Permission;
};

export const Table = ({ columns, rows, onDelete, onUpdate, className, permission }: TableProps) => {
  return (
    <>
      <table
        className={classNames(
          "table-auto border-spacing-0 w-full border border-gray-300 rounded-md",
          className
        )}
      >
        <thead className="bg-gray-50 text-left border-b border-gray-300 rounded-md">
          <tr>
            {columns.map((column) => (
              <th key={column.name} scope="col" className="p-2 text-xs font-semibold text-gray-900">
                {column.label}
              </th>
            ))}
            {(onUpdate || onDelete) && <th scope="col"></th>}
          </tr>
        </thead>

        <tbody className="bg-custom-white text-left">
          {rows.map((row, index: number) => (
            <tr
              key={index}
              className={classNames(
                "border-b border-gray-200 h-[36px]",
                row.link ? "hover:bg-gray-50 cursor-pointer" : ""
              )}
              data-cy="object-table-row"
            >
              {columns.map((column, index) => {
                return (
                  <td key={index} className="p-0">
                    {row.link && (
                      <Link
                        className="whitespace-wrap px-2 py-1 text-xs text-gray-900 flex items-center"
                        to={row.link}
                      >
                        {renderRowValue(row.values[column.name])}
                      </Link>
                    )}

                    {!row.link && (
                      <div className="whitespace-wrap px-2 py-1 text-xs text-gray-900 flex items-center">
                        {renderRowValue(row.values[column.name])}
                      </div>
                    )}
                  </td>
                );
              })}

              {(onUpdate || onDelete) && (
                <td className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <ButtonWithTooltip
                        tooltipContent="Actions"
                        tooltipEnabled
                        variant="ghost"
                        size="square"
                        className="p-4"
                        data-testid="actions-row-button"
                      >
                        <Icon icon="mdi:dots-vertical" className="" />
                      </ButtonWithTooltip>
                    </DropdownMenuTrigger>

                    <DropdownMenuContent align="end">
                      {onUpdate && (
                        <DropdownMenuItem
                          onClick={() => onUpdate(row)}
                          disabled={!permission?.update?.isAllowed}
                          data-testid="update-row-button"
                        >
                          <Icon icon="mdi:pencil" className="text-custom-blue-500" />
                          Edit
                        </DropdownMenuItem>
                      )}

                      {onDelete && (
                        <DropdownMenuItem
                          onClick={() => onDelete(row)}
                          disabled={!permission?.delete?.isAllowed}
                          data-testid="delete-row-button"
                        >
                          <Icon icon="mdi:trash-outline" className="text-red-500" />
                          Delete
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {!rows?.length && <NoDataFound message="No items" />}
    </>
  );
};

const renderRowValue = (data: string | number | tRowValue): ReactNode => {
  if (!data) return "-";

  if (typeof data === "string" || typeof data === "number") return data;

  if ("display" in data) return data.display as ReactNode;

  if ("value" in data) return data.value as ReactNode;

  if (isValidElement(data)) return data;

  return "-";
};
