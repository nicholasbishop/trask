dist:
	python3 setup.py sdist 

lint:
	python3 -m pylint *.py

format:
	python3 -m yapf -i *.py

.PHONY: dist lint format
