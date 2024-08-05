import { Combobox, tComboboxItem } from "@/components/ui/combobox";
import { useId } from "react";
import Label from "@/components/ui/label";

type GenericSelectorProps = {
  items: Array<tComboboxItem>;
  value?: string;
  onChange: (item: string) => void;
};

export const GenericSelector = (props: GenericSelectorProps) => {
  const id = useId();

  return (
    <div className="p-4 bg-gray-200">
      <Label htmlFor={id}>Select an object type</Label>
      <Combobox id={id} {...props} />
    </div>
  );
};
