import { QSP } from "@/config/qsp";
import { DateTimeParam, useQueryParam } from "use-query-params";
import { useAuth } from "./useAuth";

type Permission = {
  allow: boolean;
  message: string | null;
};
interface UsePermission {
  isAdmin: Permission;
  write: Permission;
}

export const usePermission = (): UsePermission => {
  const { isAuthenticated, permissions } = useAuth();
  const [qspDate] = useQueryParam(QSP.DATETIME, DateTimeParam);

  const isViewingPastData = !!qspDate;

  if (isViewingPastData) {
    return {
      isAdmin: {
        allow: false,
        message: "Can't edit data from the past.",
      },
      write: {
        allow: false,
        message: "Can't edit data from the past.",
      },
    };
  }

  return {
    isAdmin: {
      allow: permissions?.isAdmin ?? false,
      message: isAuthenticated ? "Admin permissions required." : null,
    },
    write: {
      allow: permissions?.write ?? false,
      message: isAuthenticated ? "Login required." : null,
    },
  };
};
