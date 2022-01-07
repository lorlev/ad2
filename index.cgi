#!/bin/sh

printf "Content-Type: text/plain"
echo

##
printf "Status: 200 OK"
echo
echo

root_path=$(dirname $(dirname $(readlink -f "$0")))
local_path="$root_path/auto.deploy"
htdocs_dir="$root_path/htdocs"
logs_dir="$root_path/server.logs"

source "$local_path/inc/functions.sh"

LoadEnv
SelfUpdate

if
	[ -n "$HTTP_X_HOOK_UUID" ] &&
	[ -n "$HTTP_X_REQUEST_UUID" ] &&
	[ "$HTTP_X_EVENT_KEY" = "repo:push" ] &&
	[ "$HTTP_CONTENT_TYPE" = "application/json" ] &&
	[ "$REQUEST_METHOD" = "POST" ]
then
	POST=$( jq '.' )

	IS_COMMITS=$(echo $POST | jq '[.push.changes[].new | select(.name == "'$(echo $GIT_BRANCH)'" and .type == "branch")] | length')

	if [ "$IS_COMMITS" -gt 0 ]; then

		printf "Status: 200 OK"
		echo
		echo

		cd $htdocs_dir

		umask 002

		eval `ssh-agent`
		ssh-add $local_path/access/access-key
		git pull 2>&1
		eval `ssh-agent -k`

		umask 0022

		if [ "$PUSH" == "Y" -o "$PUSH" == "y" ]; then
			SendPushNotification
		fi

		if [ "$EXECUTE_SCRIPT" == "Y" -o "$EXECUTE_SCRIPT" == "y" ]; then
			echo
			echo "Execute special script"

			if [ -f "$local_path/$TECH/execute.cgi" ]; then
				source "$local_path/$TECH/execute.cgi"
			fi
		fi

		if [ "$INCREASE_VERSION" == "Y" -o "$INCREASE_VERSION" == "y" ]; then
			IncreaseVersion
		fi

		FixGitBranch

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