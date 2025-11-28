from setuptools import setup, find_packages

# load requirements from requirements.txt
with open("requirements.txt") as f:
    required = f.read().splitlines()

setup(
    name="openphil_agent",
    version="0.1.0",
    description="An agent for OpenPhil",
    packages=find_packages(),
    include_package_data=True,
    install_requires=required,
)
