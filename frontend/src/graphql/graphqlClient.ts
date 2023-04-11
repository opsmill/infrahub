import { GraphQLClient } from "graphql-request";
import { CONFIG } from "../config/config";

// Checking if there's a branch specified in the URL QSP
// If it's present, use that instead of "main"
// Need to do the same for date
const params = new URL(window.location.toString()).searchParams;
const branchInQsp = params.get(CONFIG.QSP_BRANCH);
const dateInQsp = params.get(CONFIG.QSP_DATETIME);
export const graphQLClient = new GraphQLClient(CONFIG.GRAPHQL_URL(branchInQsp ? branchInQsp : "main", dateInQsp ? new Date(dateInQsp) : undefined));