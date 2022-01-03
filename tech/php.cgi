#!/bin/sh

COMPOSER="{composer}"

if [ "$COMPOSER" == "Y" -o "$COMPOSER" == "y" ]; then
	echo
	echo "Composer install"

	export HOME=../
	export COMPOSER_HOME=../.composer

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
		&>> ../server.logs/composer.output.log

	echo "Composer output writed in /composer.output.log"

	echo
	echo "Execute Artisan Commands"

	# Clear cache
	/usr/bin/php artisan cache:clear &>> ../server.logs/artisan.output.log
	/usr/bin/php artisan auth:clear-resets &>> ../server.logs/artisan.output.log

	# Clear routes cache
	/usr/bin/php artisan route:clear &>> ../server.logs/artisan.output.log
	/usr/bin/php artisan route:cache &>> ../server.logs/artisan.output.log

	# Clear config cache
	/usr/bin/php artisan config:clear &>> ../server.logs/artisan.output.log
	/usr/bin/php artisan config:cache &>> ../server.logs/artisan.output.log

	echo "Artisan output writed in /artisan.output.log"
fi