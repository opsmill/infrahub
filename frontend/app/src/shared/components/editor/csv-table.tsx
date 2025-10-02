import { classNames } from "@/shared/utils/common";

interface CsvTableProps {
  content: string;
}

const parseCSV = (csv: string): string[][] => {
  const lines = csv.trim().split("\n");
  return lines.map((line) => {
    const values: string[] = [];
    let current = "";
    let inQuotes = false;

    for (const char of line) {
      if (char === '"') {
        inQuotes = !inQuotes;
      } else if (char === "," && !inQuotes) {
        values.push(current.trim());
        current = "";
      } else {
        current += char;
      }
    }
    values.push(current.trim());
    return values;
  });
};

const cellStyle = "whitespace-nowrap border border-neutral-700 px-4 py-3";

export function CsvTable({ content }: CsvTableProps) {
  const rows = parseCSV(content);

  if (!rows[0]) {
    return <div className="text-neutral-400 text-sm">No data available</div>;
  }

  const headers = rows[0];
  const dataRows = rows.slice(1);

  return (
    <table className="border-collapse border border-neutral-700 text-sm">
      <thead className="bg-neutral-900">
        <tr>
          {headers.map((header, index) => (
            <th
              key={index}
              className={classNames(cellStyle, "font-semibold text-xs uppercase tracking-wider")}
            >
              {header}
            </th>
          ))}
        </tr>
      </thead>

      <tbody>
        {dataRows.map((row, rowIndex) => (
          <tr key={rowIndex} className="hover:bg-neutral-900">
            {row.map((cell, cellIndex) => (
              <td key={cellIndex} className={cellStyle}>
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
