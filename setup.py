# Copyright 2026 Adobe. All rights reserved.
# This file is licensed to you under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License. You may obtain a copy
# of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR REPRESENTATIONS
# OF ANY KIND, either express or implied. See the License for the specific language
# governing permissions and limitations under the License.

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
    url="https://github.com/lrosenthol/json-formula-py",
    project_urls={
        "Documentation": "https://github.com/lrosenthol/json-formula-py#readme",
        "Issues": "https://github.com/lrosenthol/json-formula-py/issues",
        "Specification": "https://opensource.adobe.com/json-formula/",
        "Reference Implementation": "https://github.com/adobe/json-formula/",
    },
    python_requires=">=3.9",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    package_data={
        "json_formula": [
            "_vendor/json_formula_js/*.js",
            "_vendor/json_formula_js/*.mjs",
            "_vendor/json_formula_js/*.json",
            "_vendor/json_formula_js/tutorial/*.js",
        ]
    },
)
