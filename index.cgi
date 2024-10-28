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
		repo_url=$(echo "$POST" | jq -r '.repository.ssh_url')
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

	LoadEnv

	IS_COMMITS=$(GetCommitsCount "$POST" "$platform" "$GIT_BRANCH")

	if [ "$IS_COMMITS" -gt 0 ]; then
		printf "Status: 200 OK"
		echo
		echo

		# Create the build directory
		build_dir="$root_path/builds/$commit_hash"
		mkdir -p "$build_dir"
		cd $build_dir

		if [ -z $(git config alias.up) ]; then
			ModifyGitConfig
		fi

		umask 002

		eval `ssh-agent` &>/dev/null
		ssh-add $local_path/access/access-key
		git clone "$repo_url" "$build_dir"
		eval `ssh-agent -k` &>/dev/null

		umask 0022

		OutputLog "Git Branch is: $(git rev-parse --abbrev-ref HEAD)"

		if [ $(git rev-parse --abbrev-ref HEAD) != $GIT_BRANCH ]; then
			FixGitBranch
		fi

		if [ -n "$STATIC_DIRS" ]; then
			for dir in $STATIC_DIRS; do
				if [ ! -d "$root_path/static/$dir" ]; then
					mkdir -p "$root_path/static/$dir"
				fi
				ln -s "$root_path/static/$dir" "$build_dir/$dir"
			done
		fi

		rm -rf "$root_path/htdocs" || true
		ln -s "$build_dir/$commit_hash" "$root_path/htdocs"

		chmod -R 775 "$build_dir/$commit_hash"
		chmod -R 775 "$root_path/htdocs"

		chown -R nginx:ftpusers "$build_dir/$commit_hash"
		chown -R nginx:ftpusers "$root_path/htdocs"

		fourth_hash=$(git rev-list --skip=3 -n 1 "$commit_hash")
		if [[ "$commit_hash" != "$fourth_hash" ]]; then
			echo
			OutputLog "Clean Up Old builds: $fourth_hash"
			rm -rf "$build_dir/$fourth_hash" || true
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
