#!/bin/bash

if [ "$COMPOSER" == "Y" -o "$COMPOSER" == "y" ]; then
	OutputLog ""
	OutputLog "Composer install"

	export HOME=$root_path
	export COMPOSER_HOME=$root_path/.composer

	/usr/bin/php \
		-d allow_url_fopen=1 \
		-d disable_functions= \
		-d suhosin.executor.include.whitelist=phar \
		/usr/local/bin/composer \
			install \
			--profile \
			--no-interaction \
			--prefer-dist \
			--no-ansi \
			--optimize-autoloader \
			--no-dev \
		&>> "$logs_dir/composer.output.log"

	OutputLog "Composer output writed in /composer.output.log"

	if [ "$ARTISAN" == "Y" -o "$ARTISAN" == "y" ]; then
		OutputLog
		OutputLog "Execute Artisan Commands"

		# Clear cache
		/usr/bin/php artisan cache:clear &>> "$logs_dir/artisan.output.log"
		/usr/bin/php artisan auth:clear-resets &>> "$logs_dir/artisan.output.log"

		# Clear routes cache
		/usr/bin/php artisan route:clear &>> "$logs_dir/artisan.output.log"
		/usr/bin/php artisan route:cache &>> "$logs_dir/artisan.output.log"

		# Clear config cache
		/usr/bin/php artisan config:clear &>> "$logs_dir/artisan.output.log"
		/usr/bin/php artisan config:cache &>> "$logs_dir/artisan.output.log"

		OutputLog "Artisan output writed in /artisan.output.log"
	fi
fi