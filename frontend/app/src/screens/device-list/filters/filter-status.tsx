import { classNames } from "@/utils/common";
import { useState } from "react";

export default function FilterStatus() {
  const [status, setStatus] = useState("");
  return (
    <>
      <label htmlFor="status" className="block text-sm font-medium text-gray-700">
        Status
      </label>
      <div className="mt-1">
        <span className="isolate inline-flex rounded-md shadow-sm">
          <button
            onClick={() => setStatus("Active")}
            type="button"
            className={classNames(
              "relative inline-flex items-center rounded-l-md border border-gray-300 bg-custom-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50",
              status === "Active"
                ? "z-10 border-custom-blue-500 outline-none ring-1 ring-custom-blue-500"
                : ""
            )}>
            Active
          </button>
          <button
            onClick={() => setStatus("Inactive")}
            type="button"
            className={classNames(
              "relative -ml-px inline-flex items-center border border-gray-300 bg-custom-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50",
              status === "Inactive"
                ? "z-10 border-custom-blue-500 outline-none ring-1 ring-custom-blue-500"
                : ""
            )}>
            Inactive
          </button>
          <button
            onClick={() => setStatus("Down")}
            type="button"
            className={classNames(
              "relative -ml-px inline-flex items-center rounded-r-md border border-gray-300 bg-custom-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50",
              status === "Down"
                ? "z-10 border-custom-blue-500 outline-none ring-1 ring-custom-blue-500"
                : ""
            )}>
            Down
          </button>
        </span>
      </div>
    </>
  );
}
