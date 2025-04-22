import { KindComboboxList } from "@/entities/nodes/object/ui/filters/kind-combobox-list";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";

export function FilterKindSelect({
  value,
  onChange,
}: { value: string | null; onChange: (value: string) => void }) {
  const schemaKindLabel = useAtomValue(schemaKindLabelState);

  return (
    <Combobox defaultOpen>
      Kind:
      <PopoverTrigger asChild>
        <div
          className={classNames(
            inputStyle,
            "has-[>:last-child:focus]:outline-hidden has-[>:last-child:focus]:ring-2 has-[>:last-child:focus]:ring-custom-blue-600/25  has-[>:last-child:focus]:border-custom-blue-600",
            "cursor-pointer min-w-[132px] max-w-[300px]"
          )}
        >
          <div className="grow flex flex-wrap gap-2">{value && schemaKindLabel[value]}</div>

          <button type="button" className="text-gray-600 outline-hidden w-3.5 h-3.5">
            <Icon icon="mdi:unfold-more-horizontal" />
          </button>
        </div>
      </PopoverTrigger>
      <ComboboxContent fitTriggerWidth={false}>
        <KindComboboxList
          onSelect={(kind) => {
            onChange(kind);
          }}
        />
      </ComboboxContent>
    </Combobox>
  );
}
