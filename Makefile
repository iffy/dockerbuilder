
.PHONY: dockerbuilder/builder dockerbuilder/builddebug


all: dockerbuilder/builder dockerbuilder/builddebug

dockerbuilder/builder:
	docker build -f Dockerfile.builder -t dockerbuilder/builder .
	docker push dockerbuilder/builder

dockerbuilder/builddebug:
	docker build -f Dockerfile.builddebug -t dockerbuilder/builddebug .
	docker push dockerbuilder/builddebug

