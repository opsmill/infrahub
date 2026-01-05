import type React from "react";

export interface SvgProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  value: string;
}

export function Svg({ value, ...props }: SvgProps) {
  return (
    <img src={`data:image/svg+xml;utf8,${encodeURIComponent(value)}`} {...props} alt="svg-image" />
  );
}
