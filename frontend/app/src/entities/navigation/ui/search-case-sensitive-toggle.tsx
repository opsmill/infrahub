import { Button, Tooltip } from "@infrahub/ui";
import { CaseSensitiveIcon } from "lucide-react";

import { classNames } from "@/shared/utils/common";

interface SearchCaseSensitiveToggleProps {
  isSelected: boolean;
  onChange: (isSelected: boolean) => void;
  className?: string;
}

export function SearchCaseSensitiveToggle({
  isSelected,
  onChange,
  className,
}: SearchCaseSensitiveToggleProps) {
  return (
    <Tooltip message="Case sensitive">
      <Button
        aria-label="Case sensitive"
        aria-pressed={isSelected}
        variant={isSelected ? "primary" : "ghost"}
        size="xs"
        shape="circle"
        onPress={() => onChange(!isSelected)}
        className={classNames("size-8 rounded", !isSelected && "text-subtle-muted", className)}
      >
        <CaseSensitiveIcon className="size-5" />
      </Button>
    </Tooltip>
  );
}
