import { Button, Modal } from "@infrahub/ui";
import { DownloadIcon, XIcon } from "lucide-react";
import React from "react";

import { classNames } from "@/shared/utils/common";

import type { Elevation, RackFace } from "@/entities/rack-elevation/domain/model/elevation";
import {
  type ExportTheme,
  type RenderedSvg,
  renderElevationSvg,
} from "@/entities/rack-elevation/domain/rules/render-elevation-svg";

type ExportFormat = "svg" | "png" | "pdf";
type FaceChoice = "both" | RackFace;

const PNG_SCALE = 2;

const FORMATS: { id: ExportFormat; label: string; description: string }[] = [
  { id: "svg", label: "SVG", description: "Vector file for Visio, draw.io or a document" },
  { id: "png", label: "PNG", description: "Image at twice the screen resolution" },
  { id: "pdf", label: "PDF", description: "Opens the print dialog; choose Save as PDF" },
];

const FACE_CHOICES: { id: FaceChoice; label: string }[] = [
  { id: "both", label: "Front and rear" },
  { id: "front", label: "Front" },
  { id: "rear", label: "Rear" },
];

const THEME_CHOICES: { id: ExportTheme; label: string }[] = [
  { id: "light", label: "Light (for printing)" },
  { id: "dark", label: "Dark (as on screen)" },
];

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

function toSvgDataUrl(svg: string) {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

function exportPng({ svg, width, height }: RenderedSvg, fileName: string) {
  const image = new Image();
  image.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = width * PNG_SCALE;
    canvas.height = height * PNG_SCALE;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.scale(PNG_SCALE, PNG_SCALE);
    context.drawImage(image, 0, 0);
    canvas.toBlob((blob) => blob && downloadBlob(blob, fileName), "image/png");
  };
  image.src = toSvgDataUrl(svg);
}

function exportPdf({ svg, width, height }: RenderedSvg, title: string) {
  const frame = document.createElement("iframe");
  frame.style.position = "fixed";
  frame.style.width = "0";
  frame.style.height = "0";
  frame.style.border = "0";
  document.body.appendChild(frame);
  const doc = frame.contentDocument;
  if (!doc) return;
  const orientation = width > height ? "landscape" : "portrait";
  doc.title = title;
  doc.head.innerHTML = `<style>@page { size: A4 ${orientation}; margin: 10mm; } html, body { margin: 0; } svg { width: 100%; height: auto; max-height: 100vh; }</style>`;
  doc.body.innerHTML = svg;
  frame.contentWindow?.focus();
  frame.contentWindow?.print();
  setTimeout(() => frame.remove(), 1000);
}

interface ExportDialogProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  elevation: Elevation;
  mappingName: string;
  matchedKeys: Set<string> | null;
}

export function ExportDialog({
  isOpen,
  onOpenChange,
  elevation,
  mappingName,
  matchedKeys,
}: ExportDialogProps) {
  const [format, setFormat] = React.useState<ExportFormat>("svg");
  const [faces, setFaces] = React.useState<FaceChoice>("both");
  const [theme, setTheme] = React.useState<ExportTheme>("light");
  const [keepFilter, setKeepFilter] = React.useState(true);

  const rendered = renderElevationSvg(elevation, {
    faces: faces === "both" ? ["front", "rear"] : [faces],
    theme,
    title: elevation.label,
    subtitle: `${mappingName} · ${elevation.height}U · exported ${new Date().toLocaleDateString()}`,
    matchedKeys: keepFilter ? matchedKeys : null,
  });
  const baseName = `${elevation.label.replace(/[^a-z0-9-_]+/gi, "-")}-elevation`;

  const handleExport = () => {
    if (format === "svg") {
      downloadBlob(new Blob([rendered.svg], { type: "image/svg+xml" }), `${baseName}.svg`);
    } else if (format === "png") {
      exportPng(rendered, `${baseName}.png`);
    } else {
      exportPdf(rendered, baseName);
    }
  };

  return (
    <Modal aria-label="Export rack elevation" isOpen={isOpen} onOpenChange={onOpenChange}>
      <div className="flex w-240 max-w-full" style={{ maxHeight: "85vh" }}>
        <div className="flex w-72 shrink-0 flex-col gap-4 overflow-auto border-r p-4">
          <div className="flex items-start justify-between">
            <h2 className="font-semibold text-lg">Export</h2>
            <Button
              size="xs"
              shape="square"
              variant="ghost"
              aria-label="Close"
              onPress={() => onOpenChange(false)}
            >
              <XIcon />
            </Button>
          </div>
          <ChoiceGroup label="Format" value={format} options={FORMATS} onChange={setFormat} />
          <ChoiceGroup label="Faces" value={faces} options={FACE_CHOICES} onChange={setFaces} />
          <ChoiceGroup label="Colors" value={theme} options={THEME_CHOICES} onChange={setTheme} />
          {matchedKeys && (
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={keepFilter}
                onChange={(event) => setKeepFilter(event.target.checked)}
              />
              Dim objects that do not match the filter
            </label>
          )}
          <p className="text-foreground-muted text-xs">
            Labels follow the Labels setting of the view. Change it before exporting to use other
            names, for example external names for a customer.
          </p>
          <Button variant="primary" className="mt-auto" onPress={handleExport}>
            <DownloadIcon />
            Export {format.toUpperCase()}
          </Button>
        </div>
        <div className="flex min-w-0 flex-1 items-start justify-center overflow-auto bg-content-muted p-4">
          <img
            src={toSvgDataUrl(rendered.svg)}
            alt={`Preview of ${elevation.label}`}
            className="max-w-full rounded-md shadow-md"
          />
        </div>
      </div>
    </Modal>
  );
}

function ChoiceGroup<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { id: T; label: string; description?: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <fieldset className="flex flex-col gap-1">
      <legend className="mb-1 font-medium text-foreground-muted text-xs uppercase tracking-wide">
        {label}
      </legend>
      {options.map((option) => (
        <label
          key={option.id}
          className={classNames(
            "flex cursor-pointer items-start gap-2 rounded-lg border px-2 py-1.5 text-sm",
            option.id === value ? "border-border-strong bg-content" : "border-transparent"
          )}
        >
          <input
            type="radio"
            name={label}
            className="mt-1"
            checked={option.id === value}
            onChange={() => onChange(option.id)}
          />
          <span>
            {option.label}
            {option.description && (
              <span className="block text-foreground-muted text-xs">{option.description}</span>
            )}
          </span>
        </label>
      ))}
    </fieldset>
  );
}
