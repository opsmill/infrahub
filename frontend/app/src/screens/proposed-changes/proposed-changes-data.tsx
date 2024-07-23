import { Badge } from "@/components/ui/badge";
import { Icon } from "@iconify-icon/react";

export const ProposedChangesData = () => {
  return (
    <div className="flex gap-2">
      <Badge className="rounded-full" variant="green">
        <Icon icon="mdi:plus-circle-outline" className="text-xs mr-1" />1
      </Badge>

      <Badge className="rounded-full" variant="red">
        <Icon icon="mdi:minus-circle-outline" className="text-xs mr-1" />1
      </Badge>

      <Badge className="rounded-full" variant="blue">
        <Icon icon="mdi:circle-arrows" className="text-xs mr-1" />1
      </Badge>

      <Badge className="rounded-full" variant="yellow">
        <Icon icon="mdi:warning-outline" className="text-xs mr-1" />1
      </Badge>
    </div>
  );
};
