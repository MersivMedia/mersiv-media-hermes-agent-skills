"""Fail CI when the sample config/env files drift from the code.

Copy to tests/test_samples.py and set PKG / SAMPLE_YAML / Config below.
Assumes: repo-root `.env.example` and `<tool>.example.yaml`, byte-identical copies
under `<pkg>/templates/`, a `Config(dict)` class that rejects unknown keys, and an
`envfile.parse_env_file(path) -> dict`.
Prove it works: delete one variable from .env.example and run the suite; it must fail
and name that variable.
"""

import re
from pathlib import Path

import pytest
import yaml

from jevrag.config import Config            # <- your config class
from jevrag.envfile import parse_env_file   # <- your .env parser

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "jevrag"                        # <- your package dir
SAMPLE_YAML = "jevrag.example.yaml"          # <- your sample name


@pytest.mark.parametrize("root_name,pkg_name", [(".env.example", "env.example"), (SAMPLE_YAML, SAMPLE_YAML)])
def test_root_samples_match_packaged_templates(root_name, pkg_name):
    assert (ROOT / root_name).read_text() == (PKG / "templates" / pkg_name).read_text()


def test_sample_yaml_loads():
    Config(yaml.safe_load((ROOT / SAMPLE_YAML).read_text()))


def test_every_commented_backend_block_is_valid():
    # blocks look like "# store:\n#   kind: x\n#   key: v\n"
    text = (ROOT / SAMPLE_YAML).read_text()
    blocks = re.findall(r"^# store:.*\n((?:#   .*\n)+)", text, re.M)
    assert blocks, "no commented store blocks found"
    for b in blocks:
        body = "".join(line[2:] + "\n" for line in b.splitlines())
        Config({"store": yaml.safe_load("store:\n" + body)["store"]})


def test_env_example_lists_every_variable_the_code_reads():
    used = set()
    for f in PKG.rglob("*.py"):
        src = f.read_text()
        used |= set(re.findall(r'os\.environ\.get\(\s*"([A-Z][A-Z0-9_]+)"', src))
        used |= set(re.findall(r'os\.getenv\(\s*"([A-Z][A-Z0-9_]+)"', src))
        used |= set(re.findall(r'"([A-Z][A-Z0-9_]*_(?:API_KEY|TOKEN|URL|HOST))"', src))
    sample = parse_env_file(ROOT / ".env.example")
    assert used, "found no environment variables in the code"
    assert used <= set(sample), f"missing from .env.example: {sorted(used - set(sample))}"
    assert all(v == "" for v in sample.values()), "the sample must ship with blank values"
