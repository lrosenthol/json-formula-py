from pathlib import Path

from setuptools import find_packages, setup


ROOT = Path(__file__).parent


setup(
    name="json-formula",
    version="0.1.0",
    description="A native Python implementation of the Adobe JSON Formula specification.",
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="OpenAI Codex",
    license="MIT",
    python_requires=">=3.9",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    package_data={
        "json_formula": [
            "_vendor/json_formula_js/*.js",
            "_vendor/json_formula_js/*.mjs",
            "_vendor/json_formula_js/*.json",
            "_vendor/json_formula_js/tutorial/*.js",
        ]
    },
)
