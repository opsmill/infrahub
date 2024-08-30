import { QSP } from "@/config/qsp";
import { DateTimeParam, useQueryParam } from "use-query-params";
import { useAuth } from "./useAuth";

interface UsePermission {
  isAdmin: boolean;
  write: {
    allow: boolean;
    message: string | null;
  };
}

export const usePermission = (): UsePermission => {
  const { isAuthenticated, permissions } = useAuth();
  const [qspDate] = useQueryParam(QSP.DATETIME, DateTimeParam);

  const isViewingPastData = !!qspDate;

  if (!isAuthenticated || isViewingPastData) {
    return {
      isAdmin: false,
      write: {
        allow: false,
        message: isAuthenticated ? "Can't edit data from the past." : "Login required.",
      },
    };
  }

  return {
    isAdmin: permissions?.isAdmin ?? false,
    write: {
      allow: permissions?.write ?? false,
      message: null,
    },
  };
};
