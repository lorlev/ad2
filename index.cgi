#!/bin/bash

printf "Content-Type: text/text"
echo

root_path=$(dirname $(dirname $(readlink -f "$0")))
local_path="$root_path/auto.deploy"
htdocs_dir="$root_path/htdocs"
logs_dir="$root_path/server.logs"

source "$local_path/inc/functions.cgi"

if {
	[ "$HTTP_CONTENT_TYPE" = "application/json" ] && 
	[ "$REQUEST_METHOD" = "POST" ]
}; then
	POST=$(jq '.' < /dev/stdin)

	# Detect platform and branch/commits extraction logic
	if [ -n "$HTTP_X_GITLAB_EVENT" ] && [ "$HTTP_X_GITLAB_EVENT" = "Push Hook" ]; then
		platform="gitlab"
		commit_hash=$(echo "$POST" | jq -r '.after')
		repo_url=$(echo "$POST" | jq -r '.repository.git_ssh_url')
	elif [ -n "$HTTP_X_EVENT_KEY" ] && [ "$HTTP_X_EVENT_KEY" = "repo:push" ]; then
		platform="bitbucket"
		commit_hash=$(echo "$POST" | jq -r '.push.changes[0].new.target.hash')
		repo_url=$(echo "$POST" | jq -r '.repository.links.clone[] | select(.name=="ssh") | .href')
	elif [ -n "$HTTP_X_GITHUB_EVENT" ] && [ "$HTTP_X_GITHUB_EVENT" = "push" ]; then
		platform="github"
		commit_hash=$(echo "$POST" | jq -r '.after')
		repo_url=$(echo "$POST" | jq -r '.repository.ssh_url')
	else
		printf "Status: 501 Not Implemented "
		echo
		echo

		echo "Unsupported platform"

		SelfUpdate
	fi

	IS_COMMITS=$(GetCommitsCount "$POST" "$platform" "$GIT_BRANCH")

	if [ "$IS_COMMITS" -gt 0 ]; then
		build_dir="$root_path/builds/$commit_hash"

		printf "Status: 200 OK"
		echo
		echo

		LoadEnv

		CloneRepository

		cd $build_dir

		if [ -z "$(git config alias.up)" ] || [ "$(git config core.fileMode)" != "false" ]; then
			ModifyGitConfig
		fi

		OutputLog "Git Branch is: $(git rev-parse --abbrev-ref HEAD)"

		if [ $(git rev-parse --abbrev-ref HEAD) != $GIT_BRANCH ]; then
			CheckoutToBranch
		fi

		if [ -n "$STATIC_DIRS" ]; then
			echo "There are static dirs: $STATIC_DIRS"

			IFS=',' read -ra DIRS <<< "$STATIC_DIRS"
			for dir in "${DIRS[@]}"; do
				if [ ! -d "$root_path/static/$dir" ]; then
					mkdir -p "$root_path/static/$dir"
					OutputLog "Created Static dir: $dir"
				fi

				# Remove any existing symlink and create a new one
				rm -f "$build_dir/$dir"
				ln -s "$root_path/static/$dir" "$build_dir/$dir"
				OutputLog "Created symlink for: $dir"
			done
			OutputLog ""
		fi

		if [ -L "$root_path/htdocs" ]; then
			OutputLog "Removing existing symlink $root_path/htdocs"
			rm -f "$root_path/htdocs" || OutputLog "Failed to remove symlink"
		elif [ -d "$root_path/htdocs" ]; then
			OutputLog "Removing existing directory $root_path/htdocs."
			rm -rf "$root_path/htdocs" || OutputLog "Failed to remove directory"
		fi

		OutputLog "Creating new symlink for $root_path/htdocs"
		ln -s "$build_dir" "$root_path/htdocs" || OutputLog "Failed to create symlink"

		chmod -R 775 "$build_dir"
		chown -R www-data:ftpusers "$build_dir"

		fourth_hash=$(git rev-list --skip=3 -n 1 "$commit_hash")
		if [[ "$commit_hash" != "$fourth_hash" ]]; then
			echo
			OutputLog "Clean Up old build: $fourth_hash"
			rm -rf "$root_path/builds/$fourth_hash" || OutputLog "Failed to remove old build"
		fi

		if [ "$EXECUTE_SCRIPT" == "Y" -o "$EXECUTE_SCRIPT" == "y" ]; then
			echo
			OutputLog "Execute special ($TECH) script"

			if [ -f "$local_path/$TECH/execute.cgi" ]; then
				source "$local_path/$TECH/execute.cgi"
			fi
		fi

		if [ "$INCREASE_VERSION" == "Y" -o "$INCREASE_VERSION" == "y" ]; then
			IncreaseVersion
		fi

		if [ "$PUSH" == "Y" -o "$PUSH" == "y" ]; then
			SendPushNotification
		fi

		GetCommitSummary
		GetServerSummary
		SelfUpdate
	else
		printf "Status: 501 Not Implemented "
		echo
		echo

		echo "Build skipped"

		SelfUpdate
	fi
else
	printf "Status: 502 Bad Gateway"
	echo
	echo

	echo "Wrong Gateway"
fi
