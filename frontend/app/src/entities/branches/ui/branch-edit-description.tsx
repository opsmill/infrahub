import { CheckIcon, PencilIcon, XIcon } from "lucide-react";
import { useRef, useState } from "react";

import { Row } from "@/shared/components/container";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useUpdateBranchMutation } from "@/entities/branches/ui/queries/update-branch.mutation";

const DESCRIPTION_MAX_LENGTH = 1000;

interface BranchEditDescriptionProps {
  branchName: string;
  currentDescription?: string | null;
  canEdit?: boolean;
}

export function BranchEditDescription({
  branchName,
  currentDescription,
  canEdit = true,
}: BranchEditDescriptionProps) {
  const { isAuthenticated } = useAuth();
  const [isEditing, setIsEditing] = useState(false);
  const [value, setValue] = useState(currentDescription ?? "");
  const [error, setError] = useState<string | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const { mutateAsync: updateBranch, isPending } = useUpdateBranchMutation();

  const showEditAffordance = canEdit && isAuthenticated;

  const resetState = (editing: boolean) => {
    setValue(currentDescription ?? "");
    setError(null);
    setIsEditing(editing);
  };

  const handleStartEdit = () => resetState(true);

  const handleCancel = () => {
    resetState(false);
    triggerRef.current?.focus();
  };

  const handleSave = async () => {
    setError(null);
    try {
      const ok = await updateBranch({ name: branchName, description: value });
      if (!ok) {
        setError("Update failed");
        return;
      }
      setIsEditing(false);
      triggerRef.current?.focus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    }
  };

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setValue(event.target.value);
    if (error) setError(null);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.nativeEvent.isComposing) return;
    if (event.key === "Enter") {
      event.preventDefault();
      handleSave();
    } else if (event.key === "Escape") {
      event.preventDefault();
      handleCancel();
    }
  };

  if (!isEditing) {
    return (
      <Row className="items-center gap-2">
        <span className={currentDescription ? undefined : "text-neutral-400"}>
          {currentDescription || "—"}
        </span>
        {showEditAffordance && (
          <Button
            ref={triggerRef}
            variant="ghost"
            size="icon"
            onClick={handleStartEdit}
            aria-label="Edit description"
            data-testid="edit-branch-description"
          >
            <PencilIcon className="size-3.5" />
          </Button>
        )}
      </Row>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <Row className="items-center gap-2">
        <Input
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          autoFocus
          disabled={isPending}
          maxLength={DESCRIPTION_MAX_LENGTH}
          aria-label="Branch description"
          data-testid="branch-description-input"
        />
        <Button
          variant="active"
          size="icon"
          onClick={handleSave}
          isLoading={isPending}
          disabled={isPending}
          aria-label="Save description"
          data-testid="save-branch-description"
        >
          <CheckIcon className="size-3.5" />
        </Button>
        <Button
          variant="outline"
          size="icon"
          onClick={handleCancel}
          aria-label="Cancel"
          data-testid="cancel-branch-description"
        >
          <XIcon className="size-3.5" />
        </Button>
      </Row>
      {error && <p className="text-red-600 text-xs">{error}</p>}
    </div>
  );
}
