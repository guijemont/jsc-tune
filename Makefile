.PHONY: all

all: Dockerfile
	docker build -t guij/opentuner .
