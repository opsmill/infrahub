type tColumn = {
  name: string;
  label: string;
};

type tRow = {
  values: any;
};

type tDetailsProps = {
  columns: tColumn[];
  row: tRow;
};

export const List = (props: tDetailsProps) => {
  const { columns, row } = props;

  return (
    <div className="flex-1">
      <dl className="divide-y divide-gray-200">
        {columns?.map((column, index) => {
          if (!row.values[column.name]) {
            return null;
          }

          return (
            <div className="p-2 grid grid-cols-3 gap-4 text-xs" key={index}>
              <dt className=" font-medium text-gray-500 flex items-center">{column.label}</dt>

              <div className="flex items-center">
                <dd className={"mt-1 text-gray-900"}>{row.values[column.name]}</dd>
              </div>
            </div>
          );
        })}
      </dl>
    </div>
  );
};
