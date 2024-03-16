import Link from "@docusaurus/Link";

export default function ReferenceLink({ title, url, openInNewTab }) {
  return (
    <Link to={url} autoAddBaseUrl {...openInNewTab && { target: "_blank" }} className="flex justify-between pagination-nav__link margin-bottom--md">
      <span>{title}</span>
      <span>{url}</span>
    </Link>
  )
};
