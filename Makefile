.PHONY: all build run test run_eval

IMAGE_NAME := openphil_agent
CONTAINER_NAME := openphil_agent
CURRENT_DIR := $(shell pwd)
UID := $(shell id -u)

build:
	docker build \
		--build-arg UID=$(UID) \
		--build-arg GID=1234 \
		--build-arg REQS="$(shell cat requirements.txt)" \
		-t $(IMAGE_NAME) \
		.

all: run test run_eval
run:
	docker run \
		--env-file .env \
		-e PYTHONPATH=/home/duser/project \
		-v $(CURRENT_DIR):/home/duser/project \
		--name $(CONTAINER_NAME) \
		--user $(UID) \
		--rm \
		$(IMAGE_NAME) \
		/bin/bash -c "python3 scripts/run.py"

test:
	docker run \
		--env-file .env \
		-e PYTHONPATH=/home/duser/project \
		-v $(CURRENT_DIR):/home/duser/project \
		--name $(CONTAINER_NAME) \
		--user $(UID) \
		--rm \
		$(IMAGE_NAME) \
		/bin/bash -c "pytest"

run_eval:
	docker run \
		--env-file .env \
		-e PYTHONPATH=/home/duser/project \
		-v $(CURRENT_DIR):/home/duser/project \
		--name $(CONTAINER_NAME) \
		--user $(UID) \
		--rm \
		$(IMAGE_NAME) \
		/bin/bash -c "python3 scripts/run_human_eval.py"
