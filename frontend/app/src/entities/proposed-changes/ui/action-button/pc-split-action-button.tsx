import { Button, type ButtonProps, Tooltip } from "@infrahub/ui";
import type React from "react";

import { Icon } from "@/shared/components/display/icon";

import type { PcActionsContextType } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";

export type PcActionAvailability = PcActionsContextType[keyof PcActionsContextType];

interface PcSplitActionButtonProps {
  label: React.ReactNode;
  variant: NonNullable<ButtonProps["variant"]>;
  onPress?: () => void;
  type?: ButtonProps["type"];
  isPending?: boolean;
  /** Disables both buttons. */
  isDisabled?: boolean;
  /** Backend availability of the action; an unavailable action disables the main button. */
  availability?: PcActionAvailability;
  /** Opens the action picker; without it the chevron is disabled. */
  onOpenMenu?: () => void;
  /** Accessible name of the chevron when it opens the picker; null leaves it unnamed. */
  menuLabel?: string | null;
  /** "fill" stretches the buttons across the picker trigger; "fit" keeps the standard button height. */
  layout?: "fill" | "fit";
}

export function PcSplitActionButton({
  label,
  variant,
  onPress,
  type,
  isPending,
  isDisabled,
  availability,
  onOpenMenu,
  menuLabel = "More actions",
  layout = "fill",
}: PcSplitActionButtonProps) {
  const isUnavailable = !!availability && !availability.available;

  const mainButton = (
    <Button
      className={
        layout === "fill"
          ? "flex h-full grow flex-wrap gap-2 rounded-r-none"
          : "flex gap-2 rounded-r-none"
      }
      onPress={onPress}
      type={type}
      variant={variant}
      isPending={isPending}
      isDisabled={isDisabled || isUnavailable || isPending}
      isDisabledAndFocusable={isUnavailable && !isPending}
    >
      {label}
    </Button>
  );

  return (
    <>
      {availability ? (
        <Tooltip
          message={isUnavailable ? availability.unavailability_reason : undefined}
          className="whitespace-pre"
        >
          {mainButton}
        </Tooltip>
      ) : (
        mainButton
      )}

      <Button
        className={
          layout === "fill" ? "h-full rounded-l-none border-l-0" : "h-9 rounded-l-none border-l-0"
        }
        variant={variant}
        size={"sm"}
        onPress={onOpenMenu}
        isDisabled={isDisabled || isPending || !onOpenMenu}
        data-testid={onOpenMenu ? "proposed-change-action-button-select" : undefined}
        aria-label={onOpenMenu ? (menuLabel ?? undefined) : undefined}
      >
        <Icon icon="mdi:unfold-more-horizontal" />
      </Button>
    </>
  );
}
