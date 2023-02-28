import { gql } from "@apollo/client";

export const GET_DEVICE_LIST = gql`
  query DeviceList {
    device {
      id
    }
  }
`;
