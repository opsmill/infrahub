import { Autocomplete, ListBox, Popover, PopoverTrigger, SelectItem } from "@infrahub/ui";
import type { ReactNode } from "react";
import { Header, ListBoxSection } from "react-aria-components";

import type { ScopeCandidate } from "@/entities/resource-manager/domain/model/scope-candidate";

interface ScopeCandidatePickerProps {
  candidates: ScopeCandidate[];
  onAdd: (name: string) => void;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  trigger: ReactNode;
}

export function ScopeCandidatePicker({
  candidates,
  onAdd,
  isOpen,
  onOpenChange,
  trigger,
}: ScopeCandidatePickerProps) {
  const sections = [
    {
      id: "relationship",
      title: "Relationships",
      items: candidates.filter((candidate) => candidate.type === "relationship"),
    },
    {
      id: "attribute",
      title: "Attributes",
      items: candidates.filter((candidate) => candidate.type === "attribute"),
    },
  ].filter((section) => section.items.length > 0);
  const disabledKeys = candidates
    .filter((candidate) => candidate.unavailableReason)
    .map((candidate) => candidate.name);

  return (
    <PopoverTrigger isOpen={isOpen} onOpenChange={onOpenChange}>
      {trigger}
      <Popover placement="bottom start" className="w-80">
        <Autocomplete>
          <ListBox
            aria-label="Scope fields"
            items={sections}
            disabledKeys={disabledKeys}
            className="max-h-80"
            onAction={(key) => {
              onAdd(String(key));
              onOpenChange(false);
            }}
          >
            {(section) => (
              <ListBoxSection id={section.id}>
                <Header className="px-2 pt-2 pb-1 font-medium text-foreground-muted text-xs">
                  {section.title}
                </Header>
                {section.items.map((candidate) => (
                  <SelectItem key={candidate.name} id={candidate.name} textValue={candidate.label}>
                    <span className="flex w-full items-baseline gap-2">
                      <span className="min-w-0 flex-1 truncate">{candidate.label}</span>
                      <span className="shrink-0 text-foreground-muted text-xs">
                        {candidate.unavailableReason ?? (
                          <span className="font-mono">{candidate.detail}</span>
                        )}
                      </span>
                    </span>
                  </SelectItem>
                ))}
              </ListBoxSection>
            )}
          </ListBox>
        </Autocomplete>
      </Popover>
    </PopoverTrigger>
  );
}
