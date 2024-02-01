from setuptools import find_packages, setup

setup(
    name="infrahub_sync",
    packages=find_packages(exclude=["infrahub_sync_tests"]),
    install_requires=[
        "dagster",
        "dagster-cloud"
    ],
    extras_require={"dev": ["dagster-webserver", "pytest"]},
)
