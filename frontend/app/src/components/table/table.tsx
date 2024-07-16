import { Button } from "@/components/buttons/button-primitive";
import { useAuth } from "@/hooks/useAuth";
import NoDataFound from "@/screens/errors/no-data-found";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router-dom";

export type tColumn = {
  name: string;
  label: string;
};

type tRow = {
  link?: string;
  values: any;
};

type tTableProps = {
  columns: tColumn[];
  rows: tRow[];
  constructLink?: Function;
  onDelete?: Function;
  onUpdate?: Function;
};

export const Table = (props: tTableProps) => {
  const { columns, rows, onDelete, onUpdate } = props;

  const auth = useAuth();

  return (
    <>
      <table className="table-auto border-spacing-0 w-full border border-gray-300 rounded-md">
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
              data-cy="object-table-row">
              {columns.map((column, index) => (
                <td key={index} className="p-0">
                  {row.link && (
                    <Link
                      className="whitespace-wrap px-2 py-1 text-xs text-gray-900 flex items-center"
                      to={row.link}>
                      {row.values[column.name] ?? "-"}
                    </Link>
                  )}

                  {!row.link && (
                    <div className="whitespace-wrap px-2 py-1 text-xs text-gray-900 flex items-center">
                      {row.values[column.name] ?? "-"}
                    </div>
                  )}
                </td>
              ))}

              {(onUpdate || onDelete) && (
                <td className="text-right">
                  {onUpdate && (
                    <Button
                      variant="ghost"
                      size="icon"
                      disabled={!auth?.permissions?.write}
                      onClick={() => onUpdate(row)}
                      data-testid="update-row-button">
                      <Icon icon="mdi:pencil" className="text-custom-blue-500" />
                    </Button>
                  )}

                  {onDelete && (
                    <Button
                      variant="ghost"
                      size="icon"
                      disabled={!auth?.permissions?.write}
                      onClick={() => onDelete(row)}
                      data-testid="delete-row-button">
                      <Icon icon="mdi:trash" className="text-red-500" />
                    </Button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {!rows?.length && <NoDataFound message="No items" className="m-auto w-full" />}
    </>
  );
};
