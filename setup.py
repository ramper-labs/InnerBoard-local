"""
Setup script for InnerBoard-local.
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

# Read requirements
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="innerboard-local",
    version="0.1.0",
    author="InnerBoard Team",
    author_email="",
    description="A 100% offline onboarding reflection coach that turns private journaling into structured signals and concrete micro-advice",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ramper-labs/InnerBoard-local",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Education",
        "Topic :: Office/Business",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "black>=24.1.1",
            "flake8>=7.0.0",
            "mypy>=1.8.0",
            "pre-commit>=3.6.2",
            "pytest>=8.0.2",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "innerboard=app.cli:cli",
            "innerboard-legacy=app.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "app": ["prompts/*.txt"],
    },
    keywords="onboarding reflection ai coach local offline privacy",
    project_urls={
        "Bug Reports": "https://github.com/ramper-labs/InnerBoard-local/issues",
        "Source": "https://github.com/ramper-labs/InnerBoard-local",
    },
)
