import Link from "@docusaurus/Link";

export default function StandoutLink({ title, url, openInNewTab }) {
  return (
    <Link to={url} autoAddBaseUrl {...openInNewTab && { target: "_blank" }} className="button button--primary button--lg margin-bottom--md">
      {title} →
    </Link>
  )
};
