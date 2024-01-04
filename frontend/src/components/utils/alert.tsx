// type AlertProps = {};

import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  LightBulbIcon,
  XCircleIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import { classNames } from "../../utils/common";
import Accordion from "../display/accordion";

export enum ALERT_TYPES {
  SUCCESS,
  INFO,
  WARNING,
  ERROR,
}

type AlertProps = {
  closeToast?: Function;
  onDismiss?: Function;
  message?: string;
  details?: string;
  type?: ALERT_TYPES;
};

export const Alert = (props: AlertProps) => {
  const {
    // Toast props
    closeToast,
    // toastProps,
    // Custom props
    message,
    details,
    onDismiss,
    type,
  } = props;

  const getIcon = () => {
    switch (type) {
      case ALERT_TYPES.SUCCESS: {
        return <CheckCircleIcon className="w-4 h-4 text-green-400" aria-hidden="true" />;
      }
      case ALERT_TYPES.INFO: {
        return (
          <InformationCircleIcon className="w-4 h-4 text-custom-blue-500" aria-hidden="true" />
        );
      }
      case ALERT_TYPES.WARNING: {
        return <ExclamationTriangleIcon className="w-4 h-4 text-yellow-400" aria-hidden="true" />;
      }
      case ALERT_TYPES.ERROR: {
        return <XCircleIcon className="w-4 h-4 text-red-400" aria-hidden="true" />;
      }
      default: {
        return <LightBulbIcon className="w-4 h-4 text-gray-400" aria-hidden="true" />;
      }
    }
  };

  const getClassName = () => {
    switch (type) {
      case ALERT_TYPES.SUCCESS: {
        return {
          container: "bg-green-50 text-green-800",
          bg: "",
          text: "text-green-800",
          button:
            "bg-green-50 p-1.5 text-green-500 hover:bg-green-100 focus:ring-green-600 focus:ring-offset-green-50",
        };
      }
      case ALERT_TYPES.INFO: {
        return {
          container: "bg-blue-50 text-custom-blue-500",
          bg: "",
          text: "text-custom-blue-500",
          button:
            "bg-blue-50 p-1.5 text-custom-blue-500 hover:bg-custom-blue-500 focus:ring-custom-blue-500 focus:ring-offset-blue-50",
        };
      }
      case ALERT_TYPES.WARNING: {
        return {
          container: "bg-yellow-50 text-yellow-800",
          bg: "",
          text: "text-yellow-800",
          button:
            "bg-yellow-50 p-1.5 text-yellow-500 hover:bg-yellow-100 focus:ring-yellow-600 focus:ring-offset-yellow-50",
        };
      }
      case ALERT_TYPES.ERROR: {
        return {
          container: "bg-red-50 text-red-800",
          bg: "",
          text: "text-red-800",
          button:
            "bg-red-50 p-1.5 text-red-500 hover:bg-red-100 focus:ring-red-600 focus:ring-offset-red-50",
        };
      }
      default: {
        return {
          container: "bg-gray-50 text-gray-800",
          bg: "",
          text: "text-gray-800",
          button:
            "bg-gray-50 p-1.5 text-gray-500 hover:bg-gray-100 focus:ring-gray-600 focus:ring-offset-gray-50",
        };
      }
    }
  };

  const handleDismiss = () => {
    closeToast && closeToast();
    onDismiss && onDismiss();
  };

  const alertClasses = getClassName();

  const alertMessage = <p className={classNames("text-sm ", alertClasses.text)}>{message}</p>;

  const alertDetails = <p className={classNames("text-sm", alertClasses.text)}>{details}</p>;

  return (
    <div className={classNames("rounded-m p-4", alertClasses.container)}>
      <div className="flex items-center">
        <div className="flex-shrink-0 flex items-start">{getIcon()}</div>
        <div className="ml-3">
          {details ? <Accordion title={alertMessage}>{alertDetails}</Accordion> : alertMessage}
        </div>
        <div className="ml-auto pl-3">
          <div className="-mx-1.5 -my-1.5">
            <button
              type="button"
              className={classNames(
                "inline-flex rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2",
                alertClasses?.button
              )}
              onClick={handleDismiss}>
              <XMarkIcon className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
