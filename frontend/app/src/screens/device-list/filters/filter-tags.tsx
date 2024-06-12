import { classNames } from "@/utils/common";
import { RadioGroup } from "@headlessui/react";
import { useState } from "react";

const colors = [
  { name: "Red", bgColor: "bg-red-500", selectedColor: "ring-red-500" },
  { name: "Green", bgColor: "bg-green-500", selectedColor: "ring-green-500" },
  { name: "Blue", bgColor: "bg-custom-blue-500", selectedColor: "ring-custom-blue-500" },
];

export default function FilterTags() {
  const [selectedColor, setSelectedColor] = useState(colors[1]);

  return (
    <RadioGroup value={selectedColor} onChange={setSelectedColor}>
      <RadioGroup.Label className="block text-sm font-medium text-gray-700">
        Choose a label color
      </RadioGroup.Label>
      <div className="mt-3 flex items-center space-x-3">
        {colors.map((color) => (
          <RadioGroup.Option
            key={color.name}
            value={color}
            className={({ active, checked }) =>
              classNames(
                color.selectedColor,
                active && checked ? "ring ring-offset-1" : "",
                !active && checked ? "ring-2" : "",
                "-m-0.5 relative p-0.5 rounded-full flex items-center justify-center cursor-pointer focus:outline-none"
              )
            }>
            <RadioGroup.Label as="span" className="sr-only">
              {color.name}
            </RadioGroup.Label>
            <span
              aria-hidden="true"
              className={classNames(
                color.bgColor,
                "h-6 w-6 border border-custom-black border-opacity-10 rounded-full"
              )}
            />
          </RadioGroup.Option>
        ))}
      </div>
    </RadioGroup>
  );
}
