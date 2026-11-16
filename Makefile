PLUGINS := $(wildcard plugins/*)

.PHONY: help test validate

help:
	@echo "make test      run every plugin's tests (plugins/*/tests)"
	@echo "make validate  check the marketplace and plugin manifests with the claude CLI"

test:
	@set -e; for p in $(PLUGINS); do \
	  if [ -d $$p/tests ]; then echo "== $$p"; python3 -m unittest discover -s $$p/tests; fi; \
	done

validate:
	claude plugin validate .
