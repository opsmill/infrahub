// PROTOTYPE design-jam schema-viewer-sections
// Section rows for the Properties tab, used from rev 3; later revisions copy it instead of editing it.
import { ChevronRightIcon } from "lucide-react";

import { Badge } from "@/shared/components/ui/badge";

import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { PropertyTitle } from "@/entities/schema/ui/styled";

import type { ViewerSection } from "./context";
import { viewerSectionsRev03 } from "./sections-rev-03";

const countLabel = (section: ViewerSection) => {
  const count = section.attributes.length + section.relationships.length;
  return count === 1 ? "1 field" : `${count} fields`;
};

const sourceLabel = (section: ViewerSection) => {
  switch (section.source.type) {
    case "builtin":
      return "default section";
    case "inherited":
      return `from ${section.source.from}`;
    default:
      return "declared here";
  }
};

export function SectionsSummaryRev03({
  schema,
  onOpenSection,
  openLabel,
}: {
  schema: ModelSchema;
  onOpenSection: (name: string) => void;
  openLabel: string;
}) {
  const sections = viewerSectionsRev03(schema);
  if (sections.length === 0) return null;

  return (
    <div>
      <PropertyTitle title="Sections" />
      <ul>
        {sections.map((section) => (
          <li key={section.name}>
            <button
              type="button"
              onClick={() => onOpenSection(section.name)}
              aria-label={`${section.label}, ${openLabel}`}
              className="group flex w-full items-start justify-between gap-4 p-2 py-3 text-left text-sm focus-visible:outline-2 focus-visible:outline-ring"
            >
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="group-hover:underline">{section.label}</span>
                  {section.collapsed && <Badge variant="gray-outline">starts collapsed</Badge>}
                </span>
                <span className="flex flex-wrap items-baseline gap-x-1.5 text-foreground-muted text-xs">
                  <span className="font-mono">{section.name}</span>
                  <span aria-hidden>·</span>
                  <span>{sourceLabel(section)}</span>
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-1 font-medium tabular-nums">
                {countLabel(section)}
                <ChevronRightIcon
                  aria-hidden
                  className="size-4 text-foreground-muted transition-colors duration-150 group-hover:text-foreground"
                />
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
