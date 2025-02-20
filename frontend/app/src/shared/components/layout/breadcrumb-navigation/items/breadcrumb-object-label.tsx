import { BreadcrumbLink } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-link";

export default function BreadcrumbObjectCustomDisplay({
  kind,
  id,
  ...props
}: {
  kind: string;
  id: string;
  className?: string;
}) {
  return <BreadcrumbLink {...props}>OK</BreadcrumbLink>;
}
