#!/bin/bash

if [ "$GUNICORN" == "Y" -o "$GUNICORN" == "y" ]; then
	OutputLog ""
	OutputLog "Sync Python requirements"

	export HOME=$root_path
	source "$htdocs_dir/bin/activate"
	pip install -r requirements.txt --cache-dir "$root_path/.pip/cache" &> "$logs_dir/pip.install.output.log"
	deactivate venv

	OutputLog "Pip output writed in /pip.install.output.log"
fi