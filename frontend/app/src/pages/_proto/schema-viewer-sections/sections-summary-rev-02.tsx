// PROTOTYPE design-jam schema-viewer-sections
// Compact section rows for the Properties tab, used from rev 2; later revisions copy it instead of editing it.
import { Badge } from "@/shared/components/ui/badge";

import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { PropertyTitle } from "@/entities/schema/ui/styled";

import { SourceTag, type ViewerSection, viewerSections } from "./context";

const countLabel = (section: ViewerSection) => {
  const count = section.attributes.length + section.relationships.length;
  return count === 1 ? "1 field" : `${count} fields`;
};

export function SectionsSummary({
  schema,
  onKindClick,
  onOpenSection,
  openLabel,
}: {
  schema: ModelSchema;
  onKindClick: (kind: string) => void;
  onOpenSection?: (name: string) => void;
  openLabel?: string;
}) {
  const sections = viewerSections(schema);
  if (sections.length === 0) return null;

  return (
    <div>
      <PropertyTitle title="Sections" />
      <ul className="divide-y">
        {sections.map((section) => (
          <li
            key={section.name}
            className="flex items-start justify-between gap-4 p-2 py-3 text-sm"
          >
            <div className="min-w-0">
              <p className="flex flex-wrap items-baseline gap-x-2">
                {onOpenSection ? (
                  <button
                    type="button"
                    onClick={() => onOpenSection(section.name)}
                    aria-label={`${section.label}, ${openLabel ?? "open"}`}
                    className="rounded-sm font-medium text-custom-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-ring dark:text-custom-blue-300"
                  >
                    {section.label}
                  </button>
                ) : (
                  <span className="font-medium">{section.label}</span>
                )}
                <span className="font-mono text-foreground-muted text-xs">{section.name}</span>
              </p>
              {section.description && (
                <p className="text-foreground-muted text-xs">{section.description}</p>
              )}
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <span className="font-medium tabular-nums">{countLabel(section)}</span>
              <span className="flex items-center gap-1.5">
                {section.source.type === "own" ? (
                  <span className="text-foreground-muted text-xs">declared here</span>
                ) : (
                  <SourceTag source={section.source} onKindClick={onKindClick} />
                )}
                {section.collapsed && <Badge variant="gray-outline">starts collapsed</Badge>}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
