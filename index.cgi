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
	# Detect platform and branch/commits extraction logic
	if [ -n "$HTTP_X_GITLAB_EVENT" ] && [ "$HTTP_X_GITLAB_EVENT" = "Push Hook" ]; then
		platform="gitlab"
	elif [ -n "$HTTP_X_EVENT_KEY" ] && [ "$HTTP_X_EVENT_KEY" = "repo:push" ]; then
		platform="bitbucket"
	elif [ -n "$HTTP_X_GITHUB_EVENT" ] && [ "$HTTP_X_GITHUB_EVENT" = "push" ]; then
		platform="github"
	else
		printf "Status: 501 Not Implemented "
		echo
		echo

		echo "Unsupported platform"

		SelfUpdate
	fi

	POST=$(jq '.' < /dev/stdin)
	LoadEnv

	# Get number of commits using the function
	IS_COMMITS=$(GetCommitsCount "$POST" "$platform" "$GIT_BRANCH")

	if [ "$IS_COMMITS" -gt 0 ]; then
		printf "Status: 200 OK"
		echo
		echo

		cd $htdocs_dir

		if [ -z $(git config alias.up) ]; then
			ModifyGitConfig
		fi

		umask 002

		eval `ssh-agent` &>/dev/null
		ssh-add $local_path/access/access-key
		git up
		eval `ssh-agent -k` &>/dev/null

		umask 0022

		if [ "$PUSH" == "Y" -o "$PUSH" == "y" ]; then
			SendPushNotification
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

		OutputLog "Git Branch is: $(git rev-parse --abbrev-ref HEAD)"

		if [ $(git rev-parse --abbrev-ref HEAD) != $GIT_BRANCH ]; then
			FixGitBranch
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
