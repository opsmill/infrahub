def test_help_message(testdir):
    """Make sure that the plugin is loaded by capturing an option it adds in the help message."""
    result = testdir.runpytest("--help")
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
