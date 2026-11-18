#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

PROJECT_DIR="$TEST_DIR/project with spaces"
mkdir -p "$TEST_DIR/bin" "$PROJECT_DIR/dev" "$PROJECT_DIR/python_sdk" \
    "$PROJECT_DIR/frontend/app" "$PROJECT_DIR/frontend/packages/schema-visualizer"
cp "$SCRIPT_DIR/setup-environment.sh" "$PROJECT_DIR/dev/"
touch "$PROJECT_DIR/python_sdk/pyproject.toml" \
    "$PROJECT_DIR/frontend/packages/schema-visualizer/package.json"

for tool in git uv pnpm gh; do
    cat > "$TEST_DIR/bin/$tool" <<'STUB'
#!/usr/bin/env bash
tool=${0##*/}
echo "$tool $*" >> "$SETUP_TEST_LOG"
case "$tool" in
    git) exit "${SETUP_TEST_GIT_STATUS:-0}" ;;
    pnpm) exit "${SETUP_TEST_PNPM_STATUS:-0}" ;;
esac
STUB
    chmod +x "$TEST_DIR/bin/$tool"
done

run_setup() {
    local expected_status=$1
    shift
    local status=0
    : > "$TEST_DIR/commands"
    env -i PATH="$TEST_DIR/bin:/usr/bin:/bin" CLAUDE_ENV_FILE=1 \
        SETUP_TEST_LOG="$TEST_DIR/commands" "$@" \
        bash "$PROJECT_DIR/dev/setup-environment.sh" > "$TEST_DIR/output" 2>&1 || status=$?
    if [ "$status" -ne "$expected_status" ]; then
        cat "$TEST_DIR/output"
        echo "Expected exit $expected_status, got $status" >&2
        exit 1
    fi
}

assert_no_success() {
    if grep -Eq 'Frontend dependencies installed|Environment setup complete!' "$TEST_DIR/output"; then
        cat "$TEST_DIR/output"
        echo "Failed setup reported success" >&2
        exit 1
    fi
}

run_setup 0
grep -q 'Environment setup complete!' "$TEST_DIR/output"
printf 'git -C %s submodule update --init --recursive\nuv sync --all-groups\npnpm install --frozen-lockfile\ngh --version\n' \
    "$PROJECT_DIR" > "$TEST_DIR/expected-commands"
diff -u "$TEST_DIR/expected-commands" "$TEST_DIR/commands"
echo "PASS: successful setup initializes submodules before installing dependencies"

run_setup 1 SETUP_TEST_PNPM_STATUS=1
assert_no_success
echo "PASS: failed frontend installation aborts setup"

for manifest in python_sdk/pyproject.toml frontend/packages/schema-visualizer/package.json; do
    rm "$PROJECT_DIR/$manifest"
    run_setup 1
    grep -Fq "Error: $manifest is missing after submodule initialization" "$TEST_DIR/output"
    assert_no_success
    if grep -Eq '^(uv|pnpm) ' "$TEST_DIR/commands"; then
        echo "Missing manifest did not prevent dependency installation" >&2
        exit 1
    fi
    touch "$PROJECT_DIR/$manifest"
    echo "PASS: missing $manifest aborts before dependency installation"
done

run_setup 1 SETUP_TEST_GIT_STATUS=1
grep -q 'Error: failed to initialize git submodules' "$TEST_DIR/output"
assert_no_success
echo "PASS: failed submodule initialization aborts setup"

run_setup 0 CLAUDE_ENV_FILE=
test ! -s "$TEST_DIR/commands"
echo "PASS: local environment skips setup"
