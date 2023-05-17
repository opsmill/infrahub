import { makeVar } from "@apollo/client";
import { Branch } from "../../generated/graphql";

export const branchVar = makeVar<Branch | null>(null);
