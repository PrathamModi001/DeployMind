from setuptools import setup, find_packages

setup(
    name="deploymind",
    version="0.1.0",
    description="Multi-agent autonomous deployment system powered by AI",
    packages=find_packages(),
    python_requires=">=3.11",
    entry_points={
        "console_scripts": [
            "deploymind=cli.main:cli",
        ],
    },
)
