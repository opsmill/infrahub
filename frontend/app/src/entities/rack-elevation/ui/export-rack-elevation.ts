const PNG_SCALE = 2;
const EXPORT_HIDDEN_SELECTOR = "[data-export-hidden]";

const downloadBlob = (blob: Blob, fileName: string) => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
};

const serializeSvg = (svg: SVGSVGElement) => {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  for (const element of clone.querySelectorAll(EXPORT_HIDDEN_SELECTOR)) {
    element.remove();
  }

  return new XMLSerializer().serializeToString(clone);
};

const loadImage = (url: string) =>
  new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("The drawing could not be converted to an image"));
    image.src = url;
  });

export const exportRackElevationSvg = (svg: SVGSVGElement, fileName: string) => {
  downloadBlob(new Blob([serializeSvg(svg)], { type: "image/svg+xml" }), fileName);
};

export const exportRackElevationPng = async (svg: SVGSVGElement, fileName: string) => {
  const { width, height } = svg.viewBox.baseVal;
  const svgUrl = URL.createObjectURL(new Blob([serializeSvg(svg)], { type: "image/svg+xml" }));

  try {
    const image = await loadImage(svgUrl);
    const canvas = document.createElement("canvas");
    canvas.width = width * PNG_SCALE;
    canvas.height = height * PNG_SCALE;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("The drawing could not be rendered on a canvas");

    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const png = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!png) throw new Error("The drawing could not be converted to a PNG file");

    downloadBlob(png, fileName);
  } finally {
    URL.revokeObjectURL(svgUrl);
  }
};

export const exportRackElevationCsv = (csv: string, fileName: string) => {
  downloadBlob(new Blob([csv], { type: "text/csv" }), fileName);
};
