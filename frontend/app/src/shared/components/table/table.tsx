import type { ReactNode } from "react";
import { Link } from "react-router";

import NoDataFound from "@/shared/components/errors/no-data-found";
import { classNames } from "@/shared/utils/common";

type tRowValue = {
  value: unknown;
  display: ReactNode;
};

export type tColumn = {
  name: string;
  label: string;
};

type tRow = {
  link?: string;
  values: Record<string, string | number | tRowValue>;
};

type TableProps = {
  columns: tColumn[];
  rows: tRow[];
  className?: string;
};

export const Table = ({ columns, rows, className }: TableProps) => {
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
          </tr>
        </thead>

        <tbody className="bg-white text-left">
          {rows.map((row, index: number) => (
            <tr
              key={index}
              className={classNames(
                "h-9 border-gray-200 border-b",
                row.link ? "cursor-pointer hover:bg-gray-50" : ""
              )}
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

  return "-";
};
