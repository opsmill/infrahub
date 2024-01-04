import { useState } from "react";
import { Input } from "../components/input";
import { FormFieldError } from "../screens/edit-form-hook/form";
import { MultipleInput } from "./multiple-input";
import { SelectOption } from "./select";

type OpsListProps = {
  label: string;
  value: (string | SelectOption)[];
  onChange: (value: (string | SelectOption)[]) => void;
  error?: FormFieldError;
  isProtected?: boolean;
};

export default function List(props: OpsListProps) {
  const { value, onChange, label, error, isProtected } = props;
  console.log("value: ", value);

  const [inputValue, sertInputValue] = useState("");

  const handleInputChange = (newValue: string) => {
    sertInputValue(newValue);
  };

  const handleKeyDown = (event: any) => {
    if (event.key === "Enter") {
      // Prevent default behaviour
      event.preventDefault();
      event.stopPropagation();

      // Build new array with unique items
      const newArray = Array.from(new Set([...value, inputValue]));
      onChange(newArray);

      // Init input
      sertInputValue("");
    }
  };

  return (
    <>
      <Input
        id={label}
        onChange={handleInputChange}
        error={error}
        disabled={isProtected}
        placeholder="Add a new item"
        className="mb-1"
        onKeyDown={handleKeyDown}
        value={inputValue}
      />
      <MultipleInput value={value} onChange={onChange} />
    </>
  );
}
