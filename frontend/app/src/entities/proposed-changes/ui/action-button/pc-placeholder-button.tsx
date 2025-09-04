import { Icon } from "@iconify-icon/react";

import { Button } from "@/shared/components/buttons/button-primitive";

export const PcPlaceholderButton = () => {
  return (
    <>
      <Button
        className="grow flex flex-wrap gap-2 h-full rounded-r-none border-r-white"
        variant={"primary"}
        disabled
      >
        Please login
      </Button>

      <Button className="h-full rounded-l-none border-l-0" variant={"primary"} size={"sm"} disabled>
        <Icon icon="mdi:unfold-more-horizontal" />
      </Button>
    </>
  );
};
