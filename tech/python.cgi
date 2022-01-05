#!/bin/sh

if [ "$GUNICORN" == "Y" -o "$GUNICORN" == "y" ]; then
	echo
	echo "Sync Python requirements"

	export HOME=$root_path
	source "$htdocs_dir/bin/activate"
	pip install -r requirements.txt --cache-dir "$root_path/.pip/cache" &> "$logs_dir/pip.install.output.log"
	deactivate venv

	echo "Pip output writed in /pip.install.output.log"
fi