export default function ReferenceLink({ title, url, openInNewTab }) {
  return (
    <a href={url} {...openInNewTab && { target: "_blank" }} className="flex justify-between pagination-nav__link margin-bottom--md">
      <span>{title}</span>
      <span>{url}</span>
    </a>
  )
};
