SERVER="dockerbuilder"

.PHONY: $(SERVER)/builder $(SERVER)/builddebug


all: $(SERVER)/builder $(SERVER)/builddebug

$(SERVER)/builder:
	docker build -f Dockerfile.builder -t $(SERVER)/builder .
	docker push $(SERVER)/builder

$(SERVER)/builddebug:
	docker build -f Dockerfile.builddebug -t $(SERVER)/builddebug .
	docker push $(SERVER)/builddebug

