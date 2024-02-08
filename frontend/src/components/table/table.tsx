import { Icon } from "@iconify-icon/react";
import { useContext } from "react";
import { Link } from "react-router-dom";
import { AuthContext } from "../../decorators/withAuth";
import NoDataFound from "../../screens/no-data-found/no-data-found";
import { classNames } from "../../utils/common";
import { BUTTON_TYPES, Button } from "../buttons/button";

type tColumn = {
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
};

export const Table = (props: tTableProps) => {
  const { columns, rows, onDelete } = props;

  const auth = useContext(AuthContext);

  return (
    <table className="table-auto border-spacing-0 w-full border border-gray-300 rounded-md">
      <thead className="bg-gray-50 text-left border-b border-gray-300 rounded-md">
        <tr>
          {columns?.map((column) => (
            <th key={column.name} scope="col" className="p-2 text-xs font-semibold text-gray-900">
              {column.label}
            </th>
          ))}
          {onDelete && <th scope="col"></th>}
        </tr>
      </thead>

      <tbody className="bg-custom-white text-left">
        {!rows?.length && <NoDataFound message="No items" className="m-auto w-full" />}

        {rows?.map((row: any, index: number) => (
          <tr
            key={index}
            className={classNames(
              "border-b border-gray-200",
              row.link ? "hover:bg-gray-50 cursor-pointer" : ""
            )}
            data-cy="object-table-row">
            {columns?.map((column, index) => (
              <td key={index} className="p-0">
                {row.link && (
                  <Link
                    className="whitespace-wrap px-2 py-1 text-xs text-gray-900 min-h-7 flex items-center"
                    to={row.link}>
                    <div className="flex-grow">{row.values[column.name]}</div>
                  </Link>
                )}

                {!row.link && (
                  <div className="whitespace-wrap px-2 py-1 text-xs text-gray-900 min-h-7 flex items-center whitespace-pre">
                    {row.values[column.name]}
                  </div>
                )}
              </td>
            ))}

            {onDelete && (
              <td className="text-right w-8">
                <Button
                  data-cy="delete"
                  disabled={!auth?.permissions?.write}
                  buttonType={BUTTON_TYPES.INVISIBLE}
                  onClick={() => {
                    onDelete(row);
                  }}>
                  <Icon icon="mdi:trash" className="text-red-500" />
                </Button>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
};
