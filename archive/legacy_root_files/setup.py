from setuptools import find_namespace_packages, setup

setup(
    name="snofokk",
    version="0.1.0",
    package_dir={"": "data/src"},
    packages=find_namespace_packages(where="data/src"),
    install_requires=[
        "pandas",
        "numpy"
    ]
)
