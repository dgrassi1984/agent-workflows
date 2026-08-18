.PHONY: help install install-repo check unbound guard-test wrappers-check wrappers-test overlay setup-repo setup-repo-test map map-check map-test

PY := uv run --quiet --with pyyaml --with jsonschema python

help:  ## show the targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | expand -t22

install:  ## install every workflow and reference skill into each agent harness
	@$(PY) scripts/gen_agent_wrappers.py

install-repo:  ## install wrappers into DIR and gitignore them
	@test -n "$(DIR)" || { echo "usage: make install-repo DIR=/path/to/repo" >&2; exit 2; }
	@$(PY) scripts/gen_agent_wrappers.py --repo "$(DIR)"

check: unbound guard-test wrappers-check wrappers-test setup-repo-test map-test map-check  ## everything CI runs

unbound:  ## fail if a procedure names something belonging to one project
	@$(PY) scripts/check_unbound.py

guard-test:  ## prove check_unbound can still fail, against a deliberately bound fixture
	@$(PY) scripts/check_unbound.py --self-test

wrappers-check:  ## fail if any harness is out of date with this repo
	@$(PY) scripts/gen_agent_wrappers.py --check

wrappers-test:  ## prove a repo install gitignores the files it added
	@$(PY) scripts/gen_agent_wrappers.py --self-test

overlay:  ## validate every project overlay found under ~/Development
	@$(PY) scripts/check_overlay.py --discover $(HOME)/Development

setup-repo:  ## write an overlay into DIR (a project checkout)
	@test -n "$(DIR)" || { echo "usage: make setup-repo DIR=/path/to/repo" >&2; exit 2; }
	@$(PY) scripts/setup_repo.py "$(DIR)"

setup-repo-test:  ## prove setup_repo still parses remotes and renders an overlay
	@$(PY) scripts/setup_repo.py --self-test

map:  ## regenerate the code map for DIR (default: this repo)
	@python3 scripts/gen_codemap.py --root $(or $(DIR),.)

map-check:  ## fail if the committed code map is behind the code
	@python3 scripts/gen_codemap.py --root $(or $(DIR),.) --check

map-test:  ## prove gen_codemap is deterministic and the extractors fire
	@python3 scripts/gen_codemap.py --self-test
