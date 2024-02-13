#!/usr/bin/env python3

import os
import subprocess
import sys
from pathlib import Path
from typing import List

import jinja2
import yaml
from wcmatch import glob

pullrequest = os.getenv("BUILDKITE_PULL_REQUEST")
base_branch = os.getenv("BUILDKITE_PULL_REQUEST_BASE_BRANCH")

diff_command = "git diff --name-only HEAD^"
if pullrequest is not None and pullrequest != "false":
    diff_command = f"git diff --name-only $(git merge-base origin/{base_branch} HEAD).."

changed_files = subprocess.run(diff_command, shell=True, check=True, capture_output=True, text=True).stdout.splitlines()

print(changed_files, file=sys.stderr)

basedir = Path(__file__).parent.parent.resolve()
filters = yaml.safe_load(Path(basedir.joinpath(".github/file-filters.yml")).read_text())


def match_filters(files: List[str], filters: List):
    def flatten(xss):
        new_list = []
        for elem in xss:
            if type(elem) is list:
                new_list = new_list + elem
            else:
                new_list.append(elem)
        return new_list

    if len(glob.globfilter(files, flatten(filters), flags=glob.GLOBSTAR | glob.BRACE)) > 0:
        return True
    return False


result = dict()
for filter_name, filter_list in filters.items():
    if pullrequest == "false":
        # Always enable all steps if not a pull request
        result[filter_name] = True
    else:
        result[filter_name] = match_filters(changed_files, filter_list)


template = jinja2.Template(Path(basedir.joinpath(".buildkite/pipeline.yml.j2")).read_text())
pipeline = template.render(result)
print(pipeline)
