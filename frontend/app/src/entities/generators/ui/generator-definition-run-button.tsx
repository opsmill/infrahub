import { PlayIcon } from "lucide-react";
import { useState } from "react";
import { Text } from "react-aria-components";
import { Link } from "react-router";
import { toast } from "react-toastify";

import { constructPath } from "@/shared/api/rest/fetch";
import { Menu, MenuItem } from "@/shared/components/aria/menu";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Button, type ButtonProps } from "@/shared/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { QSP } from "@/shared/config/qsp";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useRunGeneratorMutation } from "@/entities/generators/domain/run-generator.mutation";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";

export interface RunGeneratorActionProps {
  generatorId: string;
  groupId: string;
  size?: ButtonProps["size"];
  variant?: ButtonProps["variant"];
}

export function GeneratorDefinitionRunButton({
  generatorId,
  groupId,
  size,
  variant = "active",
}: RunGeneratorActionProps) {
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);
  const [showTargetForm, setShowTargetForm] = useState(false);
  const { isPending, mutate } = useRunGeneratorMutation();
  const { isAuthenticated } = useAuth();

  const handlePopoverOpenChange = (open: boolean) => {
    setIsPopoverOpen(open);
    setShowTargetForm(false);
  };

  const handleRunGenerator = (targetNodeIds?: string[]) => {
    mutate(
      { generatorId, targetNodeIds },
      {
        onSuccess: ({ taskId }) => {
          const url = constructPath(window.location.pathname, [
            { name: QSP.TAB, value: "tasks" },
            { name: QSP.TASK_ID, value: taskId },
          ]);

          toast(
            <Alert
              type={ALERT_TYPES.SUCCESS}
              message={
                <>
                  Generator started successfully.
                  <br />
                  <Link to={url} className="flex items-center gap-1 underline">
                    View task details
                  </Link>
                </>
              }
            />
          );
        },
      }
    );
    setIsPopoverOpen(false);
  };

  return (
    <Popover open={isPopoverOpen} onOpenChange={handlePopoverOpenChange}>
      <PopoverTrigger asChild>
        <Button
          variant={variant}
          size={size}
          isLoading={isPending}
          disabled={isPending || !isAuthenticated}
        >
          {!isPending && <PlayIcon className="mr-2 size-4" />}
          Run
        </Button>
      </PopoverTrigger>

      <PopoverContent className="min-w-[200px] max-w-sm p-1" align="end">
        {showTargetForm ? (
          <GeneratorTargetSelectionForm
            generatorId={generatorId}
            groupId={groupId}
            onSubmit={handleRunGenerator}
            onCancel={() => setShowTargetForm(false)}
          />
        ) : (
          <Menu aria-label="Run generator options">
            <MenuItem onAction={() => handleRunGenerator()} className="flex-col items-start gap-0">
              <Text slot="label" className="font-semibold">
                All targets
              </Text>
              <Text slot="description" className="text-gray-600 text-xs">
                Generate for all members in the target group
              </Text>
            </MenuItem>
            <MenuItem
              onAction={() => setShowTargetForm(true)}
              className="flex-col items-start gap-0"
            >
              <Text slot="label" className="font-semibold">
                Selected targets
              </Text>
              <Text slot="description" className="text-gray-600 text-xs">
                Choose specific members of target group
              </Text>
            </MenuItem>
          </Menu>
        )}
      </PopoverContent>
    </Popover>
  );
}

interface GeneratorTargetSelectionFormProps extends RunGeneratorActionProps {
  onSubmit: (targetNodeIds: string[]) => void;
  onCancel?: () => void;
}

export function GeneratorTargetSelectionForm({
  groupId,
  onSubmit,
  onCancel,
}: GeneratorTargetSelectionFormProps) {
  const [selectedTargetNodes, setSelectedTargetNodes] = useState<RelationshipNode[]>([]);

  const handleRemoveTarget = (nodeId: string) => {
    setSelectedTargetNodes((prev) => prev.filter((node) => node.id !== nodeId));
  };

  const handleSelect = (selectedRelationship: RelationshipNode) => {
    setSelectedTargetNodes((prev) => [...prev, selectedRelationship]);
  };

  const handleSubmit = () => {
    onSubmit(selectedTargetNodes.map((node) => node.id));
  };

  return (
    <div className="flex flex-col gap-1">
      <div className="mb-1 flex items-center justify-between">
        <h3 className="font-medium text-sm">Select target nodes</h3>
        <Button
          variant="ghost"
          size="xs"
          onClick={onCancel}
          className="h-5 p-1 text-gray-500 text-xs hover:text-gray-700"
        >
          Back
        </Button>
      </div>

      <div className="rounded-sm border border-gray-200 p-2">
        {selectedTargetNodes.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {selectedTargetNodes.map((node) => {
              const label = getNodeLabel(node);

              return (
                <Badge key={node.id} className="flex items-center gap-1">
                  {label}
                  <button
                    type="button"
                    onClick={() => handleRemoveTarget(node.id)}
                    className={classNames(
                      focusVisibleStyle,
                      "flex size-3.5 items-center justify-center rounded-full border border-transparent text-xs hover:text-gray-900"
                    )}
                    aria-label={`Remove ${label}`}
                  >
                    ×
                  </button>
                </Badge>
              );
            })}
          </div>
        ) : (
          <span className="text-gray-400">No targets selected</span>
        )}
      </div>

      <RelationshipComboboxList
        autoFocus
        className="rounded-sm border"
        peer="CoreNode"
        onSelect={handleSelect}
        filterQuery={{
          member_of_groups__ids: groupId,
        }}
        filterItem={(node) => !selectedTargetNodes.some((v) => v.id === node.id)}
      />

      <Button disabled={selectedTargetNodes.length === 0} variant="active" onClick={handleSubmit}>
        Run Generator
      </Button>
    </div>
  );
}
