from __future__ import annotations

import os

import jinja2

import infrahub.config as config
from infrahub.core.node import Node


class RFile(Node):
    @property
    def has_output_defined(self):

        if self.output_path:
            return True

        return False

    @property
    def output_filelocation(self):

        repo = self.output_repository.get()
        output_filelocation = os.path.join(repo.get_active_directory(), self.output_path.value)

        return output_filelocation

    def get_query(self, at=None):

        gql_query = self.query.get()
        query = gql_query.query.value

        return query

    def get_template_environment(self):

        repo = self.template_repository.get()

        template_full_path = os.path.join(repo.get_active_directory(), self.template_path.value)

        if not os.path.isfile(template_full_path):
            raise ValueError(f"Unable to locate the template at {template_full_path}")

        templateLoader = jinja2.FileSystemLoader(searchpath=repo.get_active_directory())
        templateEnv = jinja2.Environment(loader=templateLoader, trim_blocks=True, lstrip_blocks=True)
        return templateEnv.get_template(self.template_path.value)

    def get_rendered_template(self, at=None, params=None):

        template = self.get_template_environment()
        return template.render(**params)
