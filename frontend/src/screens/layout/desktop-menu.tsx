import { useAtomValue } from "jotai/index";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import { CONFIG } from "../../config/config";
import logo from "../../images/Infrahub-SVG-hori.svg";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { currentSchemaHashAtom } from "../../state/atoms/schema.atom";
import { fetchUrl } from "../../utils/fetch";
import LoadingScreen from "../loading-screen/loading-screen";
import DropDownMenuHeader from "./desktop-menu-header";
import { Footer } from "./footer";

export default function DesktopMenu() {
  const navigate = useNavigate();

  const branch = useAtomValue(currentBranchAtom);
  const currentSchemaHash = useAtomValue(currentSchemaHashAtom);

  const [isLoading, setIsLoading] = useState(false);
  const [menu, setMenu] = useState([]);

  const fetchMenu = async () => {
    try {
      setIsLoading(true);

      const result = await fetchUrl(CONFIG.MENU_URL(branch?.name));

      setMenu(result);

      setIsLoading(false);
    } catch (error) {
      console.error("error: ", error);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while fetching the menu" />);
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchMenu();
  }, [currentSchemaHash]);

  return (
    <div className="z-100 hidden w-64 md:visible md:inset-y-0 md:flex md:flex-col">
      <div className="flex flex-grow flex-col overflow-y-auto border-r border-gray-200 bg-custom-white">
        <div className="flex items-center cursor-pointer p-4" onClick={() => navigate("/")}>
          <img src={logo} />
        </div>
        <div className="flex flex-grow flex-col flex-1 overflow-auto">
          {isLoading && <LoadingScreen size={32} hideText />}

          {!isLoading && (
            <nav
              className="flex-1 bg-custom-white divide-y"
              aria-label="Sidebar"
              data-cy="sidebar-menu"
              data-testid="sidebar-menu">
              {menu.map((item: any, index: number) => (
                <DropDownMenuHeader
                  key={index}
                  title={item.title}
                  items={item.children}
                  icon={item.icon}
                />
              ))}
            </nav>
          )}
        </div>
      </div>

      <Footer />
    </div>
  );
}
