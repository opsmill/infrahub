import { Button, Tooltip } from "@infrahub/ui";

import { Icon } from "@/shared/components/display/icon";

import type { PermissionDecision } from "@/entities/permission/domain/model/permission";

interface EditMetadataButtonProps {
  onPress: () => void;
  permission: PermissionDecision;
}

export function EditMetadataButton({ onPress, permission }: EditMetadataButtonProps) {
  return (
    <Tooltip message={permission.message}>
      <Button
        variant="ghost"
        size="xs"
        shape="circle"
        isDisabledAndFocusable={!permission.isAllowed}
        onPress={onPress}
        aria-label="Edit metadata"
        data-testid="edit-metadata-button"
      >
        <Icon icon="mdi:pencil" className="text-custom-blue-500" />
      </Button>
    </Tooltip>
  );
}
