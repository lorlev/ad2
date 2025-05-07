#!/bin/bash

if [ "$RUN_GUNICORN" == "Y" -o "$RUN_GUNICORN" == "y" ]; then
	OutputLog ""
	OutputLog "Sync Python requirements"

	cd $build_dir_path

	export HOME=$root_path
	source "$htdocs_path/bin/activate"
	pip install -r requirements.txt --cache-dir "$root_path/.pip/cache" &> "$logs_dir/pip.install.output.log"
	deactivate venv

	OutputLog "Pip output writed in /pip.install.output.log"
fi