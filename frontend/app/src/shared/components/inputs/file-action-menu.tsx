import { DownloadIcon, LinkIcon, RefreshCwIcon, Trash2Icon } from "lucide-react";
import { useState } from "react";
import { Pressable } from "react-aria-components";
import { toast } from "react-toastify";

import {
  Menu,
  MenuItem,
  MenuPopover,
  MenuSection,
  MenuTrigger,
} from "@/shared/components/aria/menu";
import { Button } from "@/shared/components/buttons/button-primitive";
import ModalDelete from "@/shared/components/modals/modal-delete";
import { Alert, ALERT_TYPES } from "@/shared/components/ui/alert";
import { INFRAHUB_API_SERVER_URL } from "@/shared/config/config";
import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";

export interface FileActionMenuProps {
  fileName: string;
  storageId?: string;
  canEdit?: boolean;
  canDelete?: boolean;
  onReplace?: () => void;
  onDelete?: () => void;
}

export function FileActionMenu({
  fileName,
  storageId,
  canEdit = true,
  canDelete = true,
  onReplace,
  onDelete,
}: FileActionMenuProps) {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const { copyToClipboard } = useCopyToClipboard();

  const handleDownload = () => {
    if (!storageId) return;
    const downloadUrl = `${INFRAHUB_API_SERVER_URL}/api/storage/object/${storageId}`;
    window.open(downloadUrl, "_blank");
  };

  const handleCopyLink = () => {
    if (!storageId) return;
    const shareableUrl = `${INFRAHUB_API_SERVER_URL}/api/storage/object/${storageId}`;
    copyToClipboard(shareableUrl);
    toast(<Alert type={ALERT_TYPES.INFO} message="Link copied to clipboard" />);
  };

  const handleDeleteConfirm = () => {
    onDelete?.();
    setShowDeleteModal(false);
  };

  return (
    <>
      <MenuTrigger>
        <Pressable>
          <Button variant="ghost" size="icon" className="size-6">
            <span className="sr-only">Actions</span>
            <svg
              className="size-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"
              />
            </svg>
          </Button>
        </Pressable>

        <MenuPopover placement="bottom end">
          <Menu>
            {storageId && (
              <MenuSection title="Actions">
                <MenuItem onAction={handleDownload}>
                  <DownloadIcon className="size-3.5" />
                  <span>Download</span>
                </MenuItem>
                <MenuItem onAction={handleCopyLink}>
                  <LinkIcon className="size-3.5" />
                  <span>Copy shareable link</span>
                </MenuItem>
              </MenuSection>
            )}

            <MenuSection title="Manage">
              <MenuItem isDisabled={!canEdit} onAction={onReplace}>
                <RefreshCwIcon className="size-3.5" />
                <span>Replace</span>
              </MenuItem>
              <MenuItem isDisabled={!canDelete} onAction={() => setShowDeleteModal(true)}>
                <Trash2Icon className="size-3.5" />
                <span>Delete</span>
              </MenuItem>
            </MenuSection>
          </Menu>
        </MenuPopover>
      </MenuTrigger>

      <ModalDelete
        open={showDeleteModal}
        setOpen={setShowDeleteModal}
        title="Remove file"
        description={`Are you sure you want to remove "${fileName}"? This action cannot be undone.`}
        onDelete={handleDeleteConfirm}
        onCancel={() => setShowDeleteModal(false)}
        confirmLabel="Remove"
      />
    </>
  );
}
