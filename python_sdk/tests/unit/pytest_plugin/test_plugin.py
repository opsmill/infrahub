def test_help_message(pytester):
    """Make sure that the plugin is loaded by capturing an option it adds in the help message."""
    result = pytester.runpytest("--help")
    result.stdout.fnmatch_lines(["*Infrahub configuration file for the repository*"])


def test_without_config(pytester):
    """Make sure 0 tests run when test file is not found."""
    result = pytester.runpytest()
    result.assert_outcomes()


def test_emptyconfig(pytester):
    """Make sure that the plugin load the test file properly."""
    pytester.makefile(
        ".yml",
        test_empty="""
        ---
        version: "1.0"
        infrahub_tests: []
    """,
    )

    result = pytester.runpytest()
    result.assert_outcomes()


def test_rfile_config_missing_directory(pytester):
    """Make sure tests raise errors if directories are not found."""
    pytester.makefile(
        ".yml",
        test_rfile="""
        ---
        version: "1.0"
        infrahub_tests:
          - resource: "RFile"
            resource_name: "bgp_config"
            tests:
              - name: "base"
                expect: PASS
                spec:
                  kind: "rfile-unit-render"
                  directory: bgp_config/base
    """,
    )
    pytester.makefile(
        ".yml",
        infrahub_config="""
        ---
        schemas:
          - schemas/demo_edge_fabric.yml

        rfiles:
          - name: bgp_config
            description: "Template for BGP config base"
            query: "bgp_sessions"
            template_path: "templates/bgp_config.j2"

    """,
    )

    result = pytester.runpytest("--infrahub-repo-config=infrahub_config.yml")
    result.assert_outcomes(errors=1)


def test_rfile_config_missing_input(pytester):
    """Make sure tests raise errors if no inputs are provided."""
    pytester.makefile(
        ".yml",
        test_rfile="""
        ---
        version: "1.0"
        infrahub_tests:
          - resource: "RFile"
            resource_name: "bgp_config"
            tests:
              - name: "base"
                expect: PASS
                spec:
                  kind: "rfile-unit-render"
                  directory: bgp_config/base
    """,
    )
    pytester.makefile(
        ".yml",
        infrahub_config="""
        ---
        schemas:
          - schemas/demo_edge_fabric.yml

        rfiles:
          - name: bgp_config
            description: "Template for BGP config base"
            query: "bgp_sessions"
            template_path: "templates/bgp_config.j2"

    """,
    )

    pytester.mkdir("bgp_config")
    pytester.mkdir("bgp_config/base")

    result = pytester.runpytest("--infrahub-repo-config=infrahub_config.yml")
    result.assert_outcomes(errors=1)


def test_rfile_no_expected_output(pytester):
    """Make sure tests succeed if no expect outputs are provided."""
    pytester.makefile(
        ".yml",
        test_rfile="""
        ---
        version: "1.0"
        infrahub_tests:
          - resource: "RFile"
            resource_name: "bgp_config"
            tests:
              - name: "base"
                expect: PASS
                spec:
                  kind: "rfile-unit-render"
                  directory: bgp_config/base
    """,
    )
    pytester.makefile(
        ".yml",
        infrahub_config="""
        ---
        schemas:
          - schemas/demo_edge_fabric.yml

        rfiles:
          - name: bgp_config
            description: "Template for BGP config base"
            query: "bgp_sessions"
            template_path: "templates/bgp_config.j2"

    """,
    )

    pytester.mkdir("bgp_config")
    pytester.mkdir("bgp_config/base")
    pytester.makefile(".json", input='{"data": {}}')

    template_dir = pytester.mkdir("templates")
    template = pytester.makefile(
        ".j2",
        bgp_config="""
    protocols {
        bgp {
            log-up-down;
            bgp-error-tolerance;
        }
    }
    """,
    )
    pytester.run("mv", template, template_dir)

    result = pytester.runpytest("--infrahub-repo-config=infrahub_config.yml")
    result.assert_outcomes(passed=1)


def test_rfile_unexpected_output(pytester):
    """Make sure tests fail if the expected and computed outputs don't match."""
    pytester.makefile(
        ".yml",
        test_rfile="""
        ---
        version: "1.0"
        infrahub_tests:
          - resource: "RFile"
            resource_name: "bgp_config"
            tests:
              - name: "base"
                expect: PASS
                spec:
                  kind: "rfile-unit-render"
                  directory: bgp_config/base
    """,
    )
    pytester.makefile(
        ".yml",
        infrahub_config="""
        ---
        schemas:
          - schemas/demo_edge_fabric.yml

        rfiles:
          - name: bgp_config
            description: "Template for BGP config base"
            query: "bgp_sessions"
            template_path: "templates/bgp_config.j2"

    """,
    )

    pytester.mkdir("bgp_config")
    pytester.mkdir("bgp_config/base")
    pytester.makefile(".json", input='{"data": {}}')
    pytester.makefile(
        ".txt",
        output="""
    protocols {
        bgp {
            group ipv4-ibgp {
                peer-as 64545;
            }
            log-up-down;
            bgp-error-tolerance;
        }
    }
    """,
    )

    template_dir = pytester.mkdir("templates")
    template = pytester.makefile(
        ".j2",
        bgp_config="""
    protocols {
        bgp {
            log-up-down;
            bgp-error-tolerance;
        }
    }
    """,
    )
    pytester.run("mv", template, template_dir)

    result = pytester.runpytest("--infrahub-repo-config=infrahub_config.yml")
    result.assert_outcomes(failed=1)
