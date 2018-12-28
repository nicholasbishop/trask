coverage:
	python3 -m coverage run --branch --omit '*site-packages*' -m unittest discover -b tests && \
	python3 -m coverage html

dist:
	python3 setup.py sdist 

lint:
	python3 -m pylint *.py trask tests

format:
	python3 -m yapf -i *.py trask/*.py tests/*.py

test:
	python3 -m unittest discover -b tests

.PHONY: coverage dist lint format test
