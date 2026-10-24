#!/usr/bin/env python3
"""genome — a project's knowledge genome: one CLI, modules you select.

A fixed set of documentation roles, each with a mutability class, plus the
machinery that keeps them true: lint, records lifecycle, research evidence,
home-base housekeeping, multi-agent coordination, and one-call orientation
(`wake`), retrieval (`ask`) and iteration close (`close`).

Modules (declared in genome.toml `[genome] modules = [...]`; core is always on):

  core      roles, lint, doctor, wake, ask, close, archive, plans, worklog,
            register, operator questions/rulings, generated zones, budgets
  records   decisions (AD) and regressions (RG): recon-gated creation,
            amendments, supersede/merge/retire with an ID map, emitted index
  research  evidence classes on figures, quarantine register, hypotheses with
            verdicts and re-open conditions, frozen pre-registrations
  ops       housekeeping gates: ownership map, links, unreachable code, tracked
            bulk, secret scan, running-job guard
  agents    per-workflow boards with claims, the agent feed (mentions inbox)

Profiles (`genome init --profile`): software = core,records · research =
core,records,research,ops · team = core,records,agents · full = all five.

One file, stdlib only (Python >= 3.11). Finds the project root by walking up
for genome.toml (or a legacy kb.toml, read unchanged). Exit codes: 0 ok,
1 usage, 2 lint/gate/claim failure.
"""

from __future__ import annotations

import argparse
import datetime as dt
import itertools
import platform
import time
import fnmatch
import hashlib
import json
import math
import os
import re
import shlex
import subprocess
import sys
import tomllib
from contextlib import suppress
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows: Guarded falls back to an exclusive-create lock file
    fcntl = None

