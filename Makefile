lint:
	python3 -m pylint *.py

format:
	python3 -m yapf -i *.py

.PHONY: lint format
