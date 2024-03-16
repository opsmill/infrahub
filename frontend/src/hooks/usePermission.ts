import { QSP } from "../config/qsp";
import { DateTimeParam, useQueryParam } from "use-query-params";
import { useAuth } from "./useAuth";

interface UsePermission {
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
      write: {
        allow: false,
        message: isAuthenticated ? "Can't edit data from the past." : "Login required.",
      },
    };
  }

  return {
    write: {
      allow: permissions?.write ?? false,
      message: null,
    },
  };
};
