import { BreadcrumbLink } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-link";

export default function BreadcrumbObjectIdDisplay({
  id,
  link,
  ...props
}: {
  link: string;
  id: string;
  className?: string;
}) {
  return (
    <BreadcrumbLink to={`${link}/${id}`} {...props}>
      {id}
    </BreadcrumbLink>
  );
}
