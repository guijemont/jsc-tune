.PHONY: all

all: Dockerfile
	docker build --build-arg uid=`id -u` --build-arg gid=`id -g` --tag guij/opentuner .
