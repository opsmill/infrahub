import { normalizeInstanceLabel } from "@/entities/preferences/domain/rules/validate-instance-label";

const DOCUMENT_TITLE_SEPARATOR = " · ";

export function formatDocumentTitle(label: string | null, pageTitle: string): string {
  const instanceLabel = label === null ? null : normalizeInstanceLabel(label);
  return instanceLabel ? `${instanceLabel}${DOCUMENT_TITLE_SEPARATOR}${pageTitle}` : pageTitle;
}
