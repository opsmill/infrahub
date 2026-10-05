import { Button, Menu, MenuItem, MenuTrigger, Popover } from "@infrahub/ui";
import { CopyIcon, EllipsisVerticalIcon, ExternalLinkIcon } from "lucide-react";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

import { StickyRightCell } from "@/entities/nodes/object/ui/object-table/cells/style";
import type { RepositoryCommit } from "@/entities/repository/domain/model/repository";

export interface RepositoryCommitRowActionsProps {
  commit: RepositoryCommit;
  webUrl: string | null;
}

export function RepositoryCommitRowActions({ commit, webUrl }: RepositoryCommitRowActionsProps) {
  const { copyToClipboard } = useCopyToClipboard();

  const copyHash = async () => {
    await copyToClipboard(commit.hash);
    toast(<Alert message="Commit hash copied" type={ALERT_TYPES.INFO} />);
  };

  return (
    <StickyRightCell>
      <MenuTrigger>
        <Button
          size="sm"
          shape="square"
          variant="ghost"
          aria-label={`Actions for commit ${commit.short_hash}`}
        >
          <EllipsisVerticalIcon className="text-foreground-muted" />
        </Button>

        <Popover placement="bottom end">
          <Menu aria-label="Commit actions">
            <MenuItem textValue="Copy commit hash" onAction={copyHash}>
              <CopyIcon />
              <span>Copy commit hash</span>
            </MenuItem>

            {webUrl && (
              <MenuItem
                textValue="View on GitHub"
                href={webUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLinkIcon />
                <span>View on GitHub</span>
              </MenuItem>
            )}
          </Menu>
        </Popover>
      </MenuTrigger>
    </StickyRightCell>
  );
}
