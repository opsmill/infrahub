export function Svg({ value, ...props }: { value: string; className?: string }) {
  return (
    <img src={`data:image/svg+xml;utf8,${encodeURIComponent(value)}`} {...props} alt="svg-image" />
  );
}
