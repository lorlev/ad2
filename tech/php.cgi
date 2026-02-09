#!/bin/bash

[ -f "$local_path/tech/custom.cgi" ] && source "$local_path/tech/custom.cgi"

type before_tech >/dev/null 2>&1 && before_tech

artisanSafe() {
	env -i \
		PATH=/usr/local/bin:/usr/bin:/bin \
		/usr/bin/php artisan "$@"
}

if [ "$RUN_COMPOSER" == "Y" -o "$RUN_COMPOSER" == "y" ]; then
	OutputLog ""
	OutputLog "Composer install"

	export HOME=$root_path
	export COMPOSER_HOME=$root_path/.composer

	if [ ! -d "$root_path/.composer/cache" ]; then
		mkdir -p "$root_path/.composer/cache"
		chown -R www-data:www-data "$root_path/.composer"
		chmod -R 775 "$root_path/.composer"
	fi

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

	if [ "$RUN_ARTISAN" == "Y" -o "$RUN_ARTISAN" == "y" ]; then
		# Create static .env if missing
		if [ ! -f "$root_path/static/.env" ]; then
			if [ -f "$build_dir_path/.env.example" ]; then
				cp "$build_dir_path/.env.example" "$root_path/static/.env"
				OutputLog "Static .env created from .env.example"

				ln -s "$root_path/static/.env" "$build_dir_path/.env"
				OutputLog ".env symlinked from static directory"
			fi
		fi

		OutputLog
		OutputLog "Execute Artisan Commands"

		# Check APP_KEY
		APP_KEY_PRESENT=$(grep -E '^APP_KEY=base64:' "$root_path/static/.env")

		if [ -z "$APP_KEY_PRESENT" ]; then
			OutputLog "Generating APP_KEY"
			artisanSafe key:generate --force || {
				OutputLog "ERROR: Failed to generate APP_KEY"
			}
		fi

		type before_artisan >/dev/null 2>&1 && before_artisan

		artisanSafe config:cache &>> "$logs_dir/artisan.output.log"
		artisanSafe route:cache &>> "$logs_dir/artisan.output.log"
		artisanSafe optimize:clear &>> "$logs_dir/artisan.output.log"

		type after_artisan >/dev/null 2>&1 && after_artisan

		OutputLog "Artisan output writed in /artisan.output.log"
	fi
fi

type after_tech >/dev/null 2>&1 && after_tech