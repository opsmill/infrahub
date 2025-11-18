import { Icon } from "@iconify-icon/react";
import { isValidElement, type ReactNode } from "react";
import { Link } from "react-router";

import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { classNames } from "@/shared/utils/common";

import type { Permission } from "@/entities/permission/types";

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
          "w-full table-auto border-spacing-0 rounded-md border border-gray-300",
          className
        )}
      >
        <thead className="rounded-md border-gray-300 border-b bg-gray-50 text-left">
          <tr>
            {columns.map((column) => (
              <th key={column.name} scope="col" className="p-2 font-semibold text-gray-900 text-xs">
                {column.label}
              </th>
            ))}
            {(onUpdate || onDelete) && <th scope="col"></th>}
          </tr>
        </thead>

        <tbody className="bg-white text-left">
          {rows.map((row, index: number) => (
            <tr
              key={index}
              className={classNames(
                "h-[36px] border-gray-200 border-b",
                row.link ? "cursor-pointer hover:bg-gray-50" : ""
              )}
              data-cy="object-table-row"
            >
              {columns.map((column, index) => {
                return (
                  <td key={index} className="p-0">
                    {row.link && (
                      <Link
                        className="whitespace-wrap flex items-center px-2 py-1 text-gray-900 text-xs"
                        to={row.link}
                      >
                        {renderRowValue(row.values[column.name])}
                      </Link>
                    )}

                    {!row.link && (
                      <div className="whitespace-wrap flex items-center px-2 py-1 text-gray-900 text-xs">
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
