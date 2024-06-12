import { classNames } from "@/utils/common";
import { RadioGroup } from "@headlessui/react";
import { useState } from "react";

const timeOptions = [
  { name: "5m" },
  { name: "15m" },
  { name: "1h" },
  { name: "6h" },
  { name: "Now" },
];

export default function FilterTime() {
  const [time, setTime] = useState(timeOptions[2]);

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-gray-900">Time</h2>
      </div>

      <RadioGroup value={time} onChange={setTime} className="mt-1">
        <RadioGroup.Label className="sr-only"> Choose a memory option </RadioGroup.Label>
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-5">
          {timeOptions.map((option) => (
            <RadioGroup.Option
              key={option.name}
              value={option}
              className={({ active, checked }) =>
                classNames(
                  "cursor-pointer focus:outline-none",
                  active ? "ring-2 ring-offset-2 ring-custom-blue-500" : "",
                  checked
                    ? "bg-custom-blue-600 border-transparent text-custom-white hover:bg-indigo-700"
                    : "bg-custom-white border-gray-200 text-gray-900 hover:bg-gray-50",
                  "border rounded-md py-2 px-3 flex items-center justify-center text-sm font-medium uppercase sm:flex-1"
                )
              }
              disabled={false}>
              <RadioGroup.Label as="span">{option.name}</RadioGroup.Label>
            </RadioGroup.Option>
          ))}
        </div>
      </RadioGroup>
    </div>
  );
}
