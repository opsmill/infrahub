import { useNavigate } from "react-router-dom";
import logo from "../../images/Infrahub-SVG-hori.svg";
import DropDownMenuHeader from "./desktop-menu-header";
import { Footer } from "./footer";

const structure = [
  {
    title: "Objects",
    children: [
      {
        title: "Device",
        path: "/objects/CoreDevice",
      },
      {
        title: "Interfaces",
        children: [
          {
            title: "Interface L2",
            path: "/objects/InfraInterfaceL2",
          },
          {
            title: "Interface L3",
            path: "/objects/InfraInterfaceL3",
          },
          {
            title: "Other Interfaces",
            children: [
              {
                title: "Random Interface",
                path: "/objects/InfraInterface",
              },
            ],
          },
        ],
      },
    ],
  },
  {
    title: "Admin",
    children: [
      {
        title: "Scema",
        path: "/schema",
      },
      {
        title: "Groups",
        path: "/groups",
      },
    ],
  },
];

export default function DesktopMenu() {
  const navigate = useNavigate();

  return (
    <div className="z-100 hidden w-64 md:visible md:inset-y-0 md:flex md:flex-col">
      <div className="flex flex-grow flex-col overflow-y-auto border-r border-gray-200 bg-custom-white">
        <div className="flex items-center cursor-pointer p-4" onClick={() => navigate("/")}>
          <img src={logo} />
        </div>
        <div className="flex flex-grow flex-col flex-1 overflow-auto">
          <nav className="flex-1 p-1 bg-custom-white" aria-label="Sidebar">
            {structure.map((item: any, index: number) => (
              <DropDownMenuHeader key={index} title={item.title} items={item.children} />
            ))}
          </nav>
        </div>
      </div>

      <Footer />
    </div>
  );
}
