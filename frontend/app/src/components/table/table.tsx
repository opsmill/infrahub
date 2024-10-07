import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { useAuth } from "@/hooks/useAuth";
import NoDataFound from "@/screens/errors/no-data-found";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router-dom";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";

export type tColumn = {
  name: string;
  label: string;
};

export type tRow = {
  link?: string;
  values: any;
};

type TableProps = {
  columns: tColumn[];
  rows: tRow[];
  constructLink?: Function;
  onDelete?: (row: tRow) => void;
  onUpdate?: (row: tRow) => void;
  className?: string;
};

export const Table = ({ columns, rows, onDelete, onUpdate, className }: TableProps) => {
  const auth = useAuth();

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
                      >
                        <Icon icon="mdi:dots-vertical" className="" />
                      </ButtonWithTooltip>
                    </DropdownMenuTrigger>

                    <DropdownMenuContent align="end">
                      {onUpdate && (
                        <DropdownMenuItem
                          onClick={() => onUpdate(row)}
                          disabled={!auth?.permissions?.write}
                        >
                          <Icon icon="mdi:pencil" className="text-custom-blue-500" />
                          Edit
                        </DropdownMenuItem>
                      )}

                      {onDelete && (
                        <DropdownMenuItem
                          onClick={() => onDelete(row)}
                          disabled={!auth?.permissions?.write}
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

const renderRowValue = (data) => {
  if (!data) return "-";

  if (data.display) return data.display;

  if (data.value) return data.value;

  if (!data.display && !data.value && typeof data !== "object") return data;

  return "-";
};
