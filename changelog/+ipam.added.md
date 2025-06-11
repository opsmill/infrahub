We’ve started a major revamp of the IPAM to make navigation faster, improve usability and the user experience.

- New IPAM layout
- A complete breadcrumb appears to display all ancestors of current IP.
- Added caching to reduce navigation time, specially when doing back and forth.
- IPAM URLs have been reworked to be more intuitive.
- Role-based access control for IPAM views and actions.
- List view has been replaced with a new table UI:
  - New refreshed UI.
  - Schema attributes/relationships displayed in the table has been sorted to keep the most useful information first.
  - You can filter the list on any built-in IPs attributes or relationships.
  - You can do a full text search on IP prefixes and IP addresses.
  - You can delete mutiple rows, or adds/removes multiple rows to a group.
  - You can visually see the hierarchy of the IPs in the table.
  - Each IP Prefixes shows the total of member type chidren in the table.
  - You can view details/edit/delete on IP directly from the table.
  - No more pagination, the table is infinitely scrollable.

- Detailed view have been improved:
  - You can now see the IP activity logs to know who edited what and when.
  - All extended attributes and relationships are displayed.
  - Relationships tabs shows total of related objects.
  - Menu has been reworked to show the actions available on a given IP.

IP Namespaces:

- New dedicated page to display all IP Namespaces, with the addition of the total of IP prefixes/addresses on each namespace.
