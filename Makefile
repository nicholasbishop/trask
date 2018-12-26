dist:
	python3 setup.py sdist 

lint:
	python3 -m pylint *.py trask/*.py tests/*.py

format:
	python3 -m yapf -i *.py trask/*.py tests/*.py

test:
	python3 -m unittest discover -b tests

.PHONY: dist lint format test
