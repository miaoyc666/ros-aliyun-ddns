SHELL := /bin/zsh

PYTHON ?= python3
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python3
PIP := $(VENV_PYTHON) -m pip

.PHONY: help init env install run dev gunicorn check

help:
	@echo "Available targets:"
	@echo "  make init      Create .env if missing, create venv, upgrade pip, install dependencies"
	@echo "  make env       Create .env from .env.example if missing"
	@echo "  make install   Install Python dependencies into .venv"
	@echo "  make run       Load .env and start the Flask development server"
	@echo "  make dev       Alias of make run"
	@echo "  make gunicorn  Load .env and start Gunicorn on 0.0.0.0:6180"
	@echo "  make check     Run dependency and syntax checks"

init: env $(VENV)/bin/activate install

env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example. Please edit it before running the service."; \
	else \
		echo ".env already exists."; \
	fi

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)

install: $(VENV)/bin/activate
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt

run:
	set -a; source .env; set +a; $(VENV_PYTHON) app.py

dev: run

gunicorn:
	set -a; source .env; set +a; $(VENV)/bin/gunicorn -w 2 -b 0.0.0.0:6180 app:app

check:
	$(PIP) check
	DDNS_PROXY_TOKEN=dummy ALIYUN_ACCESS_KEY_ID=dummy ALIYUN_ACCESS_KEY_SECRET=dummy $(VENV_PYTHON) -m py_compile app.py
