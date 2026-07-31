SHELL := /bin/bash

PYTHON ?= python3
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python3
PIP := $(VENV_PYTHON) -m pip
DOCKER_IMAGE ?= ros-aliyun-ddns:latest
DOCKER_COMPOSE ?= $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
COMPOSE_FILE ?= docker/docker-compose.yml

.PHONY: help init env install run dev gunicorn check docker-build docker-compose-init docker-compose-version docker-compose-up docker-compose-down docker-compose-logs

help:
	@echo "Available targets:"
	@echo "  make init      Create .env if missing, create venv, upgrade pip, install dependencies"
	@echo "  make env       Create .env from .env.example if missing"
	@echo "  make install   Install Python dependencies into .venv"
	@echo "  make run       Load .env and start the Flask development server"
	@echo "  make dev       Alias of make run"
	@echo "  make gunicorn  Load .env and start Gunicorn on 0.0.0.0:6180"
	@echo "  make check     Run dependency and syntax checks"
	@echo "  make docker-build         Build the Docker image"
	@echo "  make docker-compose-init  Create docker/docker-compose.yml if missing"
	@echo "  make docker-compose-version Show the Docker Compose command in use"
	@echo "  make docker-compose-up    Start with Docker Compose"
	@echo "  make docker-compose-down  Stop Docker Compose services"
	@echo "  make docker-compose-logs  Follow Docker Compose logs"

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
	$(PIP) install -r requirements.txt -c constraints.txt

run:
	set -a; source .env; set +a; $(VENV_PYTHON) app.py

dev: run

gunicorn:
	set -a; source .env; set +a; $(VENV)/bin/gunicorn -w 2 -b 0.0.0.0:6180 app:app

check:
	$(PIP) check
	DDNS_PROXY_TOKEN=dummy ALIYUN_ACCESS_KEY_ID=dummy ALIYUN_ACCESS_KEY_SECRET=dummy $(VENV_PYTHON) -m py_compile app.py docker/healthcheck.py

docker-build:
	docker build -f docker/Dockerfile -t $(DOCKER_IMAGE) .

docker-compose-init:
	@if [ ! -f docker/docker-compose.yml ]; then \
		cp docker/docker-compose.yml.example docker/docker-compose.yml; \
		echo "Created docker/docker-compose.yml from docker/docker-compose.yml.example."; \
	else \
		echo "docker/docker-compose.yml already exists."; \
	fi

docker-compose-version:
	$(DOCKER_COMPOSE) version

docker-compose-up: docker-compose-init
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) up -d --build

docker-compose-down: docker-compose-init
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) down

docker-compose-logs: docker-compose-init
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) logs -f
