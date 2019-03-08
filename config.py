#!/usr/bin/env python

import yaml

with open("settings.yaml", "r") as f:
    settings = yaml.safe_load(f)
