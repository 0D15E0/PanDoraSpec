# Makefile for local development
# Usage:
#   make install   - Install the package in editable mode
#   make test      - Run tests
#   make build     - Build the package
#   make all       - Run install, test, and build

# Use bash to support 'source'
SHELL := /bin/bash

# Activation command
ACTIVATE = source ./myenv/bin/activate

.PHONY: install test build all

install:
	@echo "Installing package in editable mode..."
	$(ACTIVATE) && pip install -e .

test:
	@echo "Running tests..."
	$(ACTIVATE) && pytest

build:
	@echo "Building package..."
	rm -rf dist/
	$(ACTIVATE) && python -m build

all: install test build
