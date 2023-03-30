import { Popover, Transition } from "@headlessui/react";
import { InformationCircleIcon } from "@heroicons/react/24/outline";
import { formatDistance } from "date-fns";
import { useAtom } from "jotai";
import { Fragment } from "react";
import { useNavigate } from "react-router-dom";
import { schemaKindNameState } from "../state/atoms/schemaKindName.atom";

export type TooltipDetailItemType = "date" | "text" | "link";

interface TooltipListItem {
    label: string;
    type: TooltipDetailItemType;
    value: any;
}

interface Props {
    items: TooltipListItem[];
}

export default function MetaDetailsTooltip(props: Props) {
  const navigate = useNavigate();
  const [schemaKindName] = useAtom(schemaKindNameState);
  const navigateToObjectDetailsPage = (obj: any) => {
    navigate(`/objects/${schemaKindName[obj.__typename]}/${obj.id}`);
  };

  return <Popover className="relative mt-1.5 ml-2">
    <Popover.Button>
      <InformationCircleIcon className="w-5 h-5" />
    </Popover.Button>
    <Transition
      as={Fragment}
      enter="transition ease-out duration-200"
      enterFrom="opacity-0 translate-y-1"
      enterTo="opacity-100 translate-y-0"
      leave="transition ease-in duration-150"
      leaveFrom="opacity-100 translate-y-0"
      leaveTo="opacity-0 translate-y-1"
    >
      <Popover.Panel className="absolute z-10 bg-white rounded-lg border shadow-xl">
        <div className="w-80 text-sm divide-y px-4">
          {props.items.map(item => {
            return <div key={item.label} className="flex justify-between w-full py-4">
              <div>{item.label}: </div>
              {item.type === "date" && item.value && <div>
                {formatDistance(
                  new Date(item.value),
                  new Date(),
                  { addSuffix: true }
                )}
              </div>}

              {item.type === "link" && <div
                className="underline cursor-pointer"
                onClick={() =>
                  navigateToObjectDetailsPage(
                    item.value
                  )
                }
              >
                {item.value?.display_label}
              </div>}

              {item.type === "text" && <div>
                {item.value}
              </div>}
            </div>;
          })}
        </div>
      </Popover.Panel>
    </Transition>
  </Popover>;
}