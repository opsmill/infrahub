import {
  BoltIcon,
  ChartBarIcon,
  CpuChipIcon,
  LinkIcon,
  ListBulletIcon,
  WifiIcon,
} from "@heroicons/react/24/outline";

export const navigation = [
  { name: "Dashboard", icon: ListBulletIcon, current: true, href: "#" },
  {
    name: "Connections",
    icon: LinkIcon,
    current: false,
    children: [
      { name: "Cables", href: "#" },
      { name: "Wireless Links", href: "#" },
      { name: "Interface Connections", href: "#" },
      { name: "Console Connections", href: "#" },
      { name: "Power Connections", href: "#" },
    ],
  },
  {
    name: "Wireless",
    icon: WifiIcon,
    current: false,
    children: [
      { name: "Wireless LANs", href: "#" },
      { name: "Wireless LAN Groups", href: "#" },
    ],
  },
  {
    name: "Power",
    icon: BoltIcon,
    current: false,
    children: [
      { name: "Power Feeds", href: "#" },
      { name: "Power Panels", href: "#" },
    ],
  },
  {
    name: "Virtualization",
    icon: CpuChipIcon,
    current: false,
    children: [
      { name: "Virtual Machines", href: "#" },
      { name: "Interfaces", href: "#" },
      { name: "Clusters", href: "#" },
      { name: "Cluster Types", href: "#" },
      { name: "Cluster Groups", href: "#" },
    ],
  },
  {
    name: "Reports",
    icon: ChartBarIcon,
    current: false,
    children: [
      { name: "Overview", href: "#" },
      { name: "Devices", href: "#" },
      { name: "Settings", href: "#" },
    ],
  },
];

export const userNavigation = [{ name: "Your Profile", href: "/profile" }];
