#!/bin/sh
# Create the Grafana service account that the Grafana MCP server uses, and store its token.
#
# Grafana cannot create a service account from a provisioning file, so this script
# calls the Grafana API once at each start. It can run again at any time: it keeps a
# stored token that still works, and replaces one that is lost or refused. It never
# prints a token or a password.
#
# The observability Helm chart of opsmill/infrahub-helm ships a copy of this file.
# The two copies must stay the same: change both in step.
#
# Needs curl, sed and grep, which the Grafana image has.
#
# Settings (environment variables):
#   GRAFANA_URL                    Address of Grafana, for example http://infrahub-grafana:3000
#   GRAFANA_ADMIN_USER             Grafana admin user
#   GRAFANA_ADMIN_PASSWORD         Its password
#   GRAFANA_MCP_TOKEN_FILE         File that receives the token
#   GRAFANA_MCP_TOKEN_FILE_OWNER   Optional "uid:gid" that must own the token file
#   GRAFANA_MCP_ROLE               Role of the service account (default: Viewer)
#   GRAFANA_WAIT_SECONDS           How long to wait for Grafana (default: 300)
set -eu

account_name="infrahub-grafana-mcp"
token_name="infrahub-grafana-mcp"
grafana_url="${GRAFANA_URL%/}"
admin_user="${GRAFANA_ADMIN_USER}"
admin_password="${GRAFANA_ADMIN_PASSWORD}"
token_file="${GRAFANA_MCP_TOKEN_FILE}"
token_file_owner="${GRAFANA_MCP_TOKEN_FILE_OWNER:-}"
role="${GRAFANA_MCP_ROLE:-Viewer}"
wait_seconds="${GRAFANA_WAIT_SECONDS:-300}"
poll_seconds=2
request_seconds=30

# No file created here is readable by another user.
umask 077

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
body_file="$work_dir/body"

fail() {
    echo "$1" >&2
    exit 1
}

# curl reads the admin credentials from this file, so the password is not in the process arguments.
escape_for_curl_config() {
    printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}
admin_config="$work_dir/admin.curlrc"
printf 'user = "%s:%s"\n' "$(escape_for_curl_config "$admin_user")" "$(escape_for_curl_config "$admin_password")" > "$admin_config"

# Call the Grafana API as the admin user. Writes the answer to $body_file and prints the HTTP status.
# A request that gets no answer prints 000.
admin_request() {
    method="$1"
    path="$2"
    data="${3:-}"
    if [ -n "$data" ]; then
        set -- --header "Content-Type: application/json" --data "$data"
    else
        set --
    fi
    curl --silent --show-error --max-time "$request_seconds" --config "$admin_config" \
        --request "$method" --output "$body_file" --write-out '%{http_code}' "$@" "$grafana_url$path" 2>/dev/null || true
}

# Stop with the message of the refused login, or with the failed call and its status.
check_status() {
    status="$1"
    action="$2"
    case "$status" in
        2??) return 0 ;;
        401) fail "Grafana refused the admin login: set INFRAHUB_GRAFANA_ADMIN_USER and INFRAHUB_GRAFANA_ADMIN_PASSWORD" ;;
        *) fail "Grafana answered HTTP $status when asked to $action" ;;
    esac
}

# Print the JSON objects of $body_file whose "name" is exactly $1, one per line.
# The objects that this script reads have no nested object.
objects_named() {
    { grep -o '{[^{}]*}' "$body_file" || true; } | { grep -F "\"name\":\"$1\"" || true; }
}

# Print the value of the numeric field $1 of the JSON object read on standard input.
number_field() {
    sed -n "s/.*\"$1\":\([0-9][0-9]*\).*/\1/p" | head -n 1
}

# Print the value of the text field $1 of the JSON object read on standard input.
text_field() {
    sed -n "s/.*\"$1\":\"\([^\"]*\)\".*/\1/p" | head -n 1
}

wait_for_grafana() {
    case "$wait_seconds" in
        "" | *[!0-9]*) fail "GRAFANA_WAIT_SECONDS must be a number of seconds, not $wait_seconds" ;;
    esac
    # The limit counts the time of the requests too, not only the pauses between them.
    deadline=$(($(date +%s) + wait_seconds))
    while true; do
        status="$(curl --silent --max-time "$poll_seconds" --output /dev/null --write-out '%{http_code}' "$grafana_url/api/health" 2>/dev/null || true)"
        if [ "$status" = 200 ]; then
            return 0
        fi
        if [ "$(date +%s)" -ge "$deadline" ]; then
            if [ "$wait_seconds" -eq 300 ]; then
                fail "Grafana did not answer at $grafana_url within 5 minutes"
            fi
            fail "Grafana did not answer at $grafana_url within $wait_seconds seconds"
        fi
        sleep "$poll_seconds"
    done
}

# True when the stored token exists and Grafana accepts it. False when there is none, or Grafana refuses it.
# Any other answer stops the script: a token that may still be valid is not replaced because of a temporary error.
stored_token_works() {
    [ -s "$token_file" ] || return 1
    token_config="$work_dir/token.curlrc"
    printf 'header = "Authorization: Bearer %s"\n' "$(escape_for_curl_config "$(cat "$token_file")")" > "$token_config"
    status="$(curl --silent --max-time "$request_seconds" --config "$token_config" --output /dev/null --write-out '%{http_code}' "$grafana_url/api/user" 2>/dev/null || true)"
    rm -f "$token_config"
    case "$status" in
        200) return 0 ;;
        401 | 403) return 1 ;;
        *) fail "Grafana answered HTTP $status when asked to check the stored token of the service account $account_name" ;;
    esac
}

wait_for_grafana

# Find the service account, or create it.
status="$(admin_request GET "/api/serviceaccounts/search?query=$account_name&perpage=1000")"
check_status "$status" "list the service accounts"
account="$(objects_named "$account_name" | head -n 1)"
if [ -z "$account" ]; then
    status="$(admin_request POST "/api/serviceaccounts" "{\"name\":\"$account_name\",\"role\":\"$role\"}")"
    check_status "$status" "create the service account $account_name"
    account="$(cat "$body_file")"
    echo "Created the Grafana service account $account_name with the $role role"
fi
account_id="$(printf '%s' "$account" | number_field id)"
[ -n "$account_id" ] || fail "Grafana gave no ID for the service account $account_name"

# An account that had another role gets the expected one, also when its token still works.
current_role="$(printf '%s' "$account" | text_field role)"
if [ "$current_role" != "$role" ]; then
    status="$(admin_request PATCH "/api/serviceaccounts/$account_id" "{\"role\":\"$role\"}")"
    check_status "$status" "give the $role role to the service account $account_name"
    echo "Changed the role of the Grafana service account $account_name from $current_role to $role"
fi

if stored_token_works; then
    echo "The stored token of the Grafana service account $account_name still works: nothing to do"
    exit 0
fi

# Grafana shows a token only when it creates it, so a lost token is replaced.
status="$(admin_request GET "/api/serviceaccounts/$account_id/tokens")"
check_status "$status" "list the tokens of the service account $account_name"
for token_id in $(objects_named "$token_name" | sed -n 's/.*"id":\([0-9][0-9]*\).*/\1/p'); do
    status="$(admin_request DELETE "/api/serviceaccounts/$account_id/tokens/$token_id")"
    check_status "$status" "delete the old token of the service account $account_name"
done

status="$(admin_request POST "/api/serviceaccounts/$account_id/tokens" "{\"name\":\"$token_name\"}")"
check_status "$status" "create a token for the service account $account_name"
grep -q '"key":"[^"]' "$body_file" || fail "Grafana gave no token for the service account $account_name"

# The token goes from Grafana's answer to its file without passing through a variable or the output.
mkdir -p "$(dirname "$token_file")"
new_token_file="$token_file.new"
rm -f "$new_token_file"
sed -n 's/.*"key":"\([^"]*\)".*/\1/p' "$body_file" | tr -d '\n' > "$new_token_file"
chmod 400 "$new_token_file"
if [ -n "$token_file_owner" ]; then
    chown "$token_file_owner" "$new_token_file"
fi
mv -f "$new_token_file" "$token_file"

echo "Stored a new token for the Grafana service account $account_name"
