# run this first in order not to mess up with your local python dependencies
start-venv:
	pipenv shell

lint:
	pycodestyle --first chaosaws


pip-install:
	pip3 install -r requirements.txt

pip-install-dev: pip-install
	pip3 install -r requirements-dev.txt

pip-clean:
	pipenv clean

pip-clean-install: pip-clean pip-install

pip-install-all: pip-install pip-install-dev

test:
	python3 setup.py pytest
