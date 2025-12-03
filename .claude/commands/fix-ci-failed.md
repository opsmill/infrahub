Please analyze and fix the GitHub CI job issue for a given branch.

Follow these steps:

1. Use this shell script to pull the failed logs from the Github CI job. The first argument to the script should be the current checked out branch, which you can retrieve using the shell command `git rev-parse --abbrev-ref HEAD`.

```bash
BRANCH=$1
RUN_ID=$(gh run list --branch $BRANCH -w CI --json databaseId,conclusion,status --jq '.[0] | select(.conclusion=="failure") | .databaseId')

JOB_ID=$( gh run view $RUN_ID --json jobs --jq '.jobs[] | select(.conclusion=="failure") | .databaseId')

gh run view -v --log-failed --job $JOB_ID
```

2. Understand the problem described in the logs
3. Search the codebase for relevant files
4. Come up with a plan first and ask for my review
5. Implement the necessary changes to fix the issue
6. Run tests to verify the fix
7. Ensure code passes linting and type checking

Remember to use the GitHub CLI (gh) for all GitHub-related tasks.
