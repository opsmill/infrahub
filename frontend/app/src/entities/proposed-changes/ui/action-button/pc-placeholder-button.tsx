import { Button } from "@infrahub/ui";

import { Icon } from "@/shared/components/display/icon";

export const PcPlaceholderButton = () => {
  return (
    <>
      <Button
        className="flex h-full grow flex-wrap gap-2 rounded-r-none border-r-white"
        variant={"primary"}
        isDisabled
      >
        Please login
      </Button>

      <Button
        className="h-full rounded-l-none border-l-0"
        variant={"primary"}
        size={"sm"}
        isDisabled
      >
        <Icon icon="mdi:unfold-more-horizontal" />
      </Button>
    </>
  );
};
