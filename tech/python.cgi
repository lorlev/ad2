#!/bin/sh

GUNICORN='{gunicorn}'

if [ "$GUNICORN" == "Y" -o "$GUNICORN" == "y" ]; then
	echo
	echo "Sync Python requirements"

	export HOME=../
	source ../htdocs/bin/activate
	pip install -r requirements.txt --cache-dir ../.pip/cache &> ../server.logs/pip.install.output.log
	deactivate venv

	echo "Pip output writed in /pip.install.output.log"
fi