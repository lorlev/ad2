#!/bin/bash

printf "Content-Type: text/text"
echo

root_path=$(dirname $(dirname $(readlink -f "$0")))
local_path="$root_path/auto.deploy"
htdocs_dir="$root_path/htdocs"
logs_dir="$root_path/server.logs"

source "$local_path/inc/functions.cgi"

SelfUpdate

if {
	# Common checks for all platforms
	[ "$HTTP_CONTENT_TYPE" = "application/json" ] &&
	[ "$REQUEST_METHOD" = "POST" ]
} && {
	# GitLab check
	[ -n "$HTTP_X_GITLAB_EVENT" ] && [ "$HTTP_X_GITLAB_EVENT" = "Push Hook" ]
} || {
	# Bitbucket check
	[ -n "$HTTP_X_EVENT_KEY" ] && [ "$HTTP_X_EVENT_KEY" = "repo:push" ]
} || {
	# GitHub check
	[ -n "$HTTP_X_GITHUB_EVENT" ] && [ "$HTTP_X_GITHUB_EVENT" = "issues" ]
}; then
	POST=$(jq '.' < /dev/stdin)

	LoadEnv

	IS_COMMITS=$(echo $POST | jq '[.push.changes[].new | select(.name == "'$(echo $GIT_BRANCH)'" and .type == "branch")] | length')

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

		OutputLog "Git Btanch is: $(git rev-parse --abbrev-ref HEAD)"

		if [ $(git rev-parse --abbrev-ref HEAD) != $GIT_BRANCH ]; then
			FixGitBranch
		fi

		GetCommitSummary
		GetServerSummary
	else
		printf "Status: 501 Not Implemented "
		echo
		echo

		echo "Build skipped"
	fi
else
	printf "Status: 502 Bad Gateway"
	echo
	echo

	echo "Wrong Gateway"
fi