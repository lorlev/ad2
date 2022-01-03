#!/bin/sh

printf "Content-Type: text/plain"
echo

##
printf "Status: 200 OK"
echo
echo

script=$(readlink -f "$0")
local_path=$(dirname "$script")

source "$local_path/inc/functions.sh"

LoadEnv

echo 1
echo $TMP_DIR
##

if
	[ -n "$HTTP_X_HOOK_UUID" ] &&
	[ -n "$HTTP_X_REQUEST_UUID" ] &&
	[ "$HTTP_X_EVENT_KEY" = "repo:push" ] &&
	[ "$HTTP_CONTENT_TYPE" = "application/json" ] &&
	[ "$REQUEST_METHOD" = "POST" ]
then
	POST=$( jq '.' )
	BRANCH='production'
	SCRIPT=$(readlink -f "$0")
	LOCAL_PATCH=$(dirname "$SCRIPT")

	if [ $HOSTNAME = "test.server" ]; then
		BRANCH='test'
	fi

	IS_COMMITS=$(echo $POST | jq '[.push.changes[].new | select(.name == "'$(echo $BRANCH)'" and .type == "branch")] | length')

	if [ "$IS_COMMITS" -gt 0 ]; then

		printf "Status: 200 OK"
		echo
		echo

		cd ../htdocs

		umask 002

		eval `ssh-agent`
		ssh-add ../auto.deploy/access-key
		git pull 2>&1
		eval `ssh-agent -k`

		umask 0022

		PUSH="{push}"
		PUSH_URL="{push_url}"
		PUSH_SECRET="{push_secret}"

		if [ "$PUSH" == "Y" -o "$PUSH" == "y" ]; then
			COMMENT=$(echo $POST | jq -r '.push.changes[].new | select(.name == "'$(echo $BRANCH)'" and .type == "branch") | .target.message')
			COMMENT=$(echo $COMMENT | sed ':a;s/\\n/<br>/g') #Clear New Lines
			AUTHOR=$(echo $POST | jq -r '.actor.display_name')
			REPOSITORY=$(echo $POST | jq -r '.repository.name')
			URL=$(echo $POST | jq -r '.push.changes[].new | select(.name == "'$(echo $BRANCH)'" and .type == "branch") | .target.links.html.href')

			echo
			echo "Send Push Notification "

			MESSAGE_RESULT=$(curl -s -X GET \
				-H "Content-Type: application/json" \
				"$PUSH_URL?key=$PUSH_SECRET&repository=$REPOSITORY&branch=$BRANCH&author=$AUTHOR&commit=$COMMENT&action_url=$URL")

			MESSAGE_IS_SEND=$(echo $MESSAGE_RESULT | jq -r '.type')
			if [ "$MESSAGE_IS_SEND" == "error" ]; then
				echo "Message don't send"
				echo $MESSAGE_RESULT
			else
				echo "Message send OK"
			fi

		fi

		echo
		echo "Your remote address is: ${REMOTE_ADDR}"
		echo "Server time is: $(date)"
		echo "Git Btanch is: $(git rev-parse --abbrev-ref HEAD)"

		if [ $(git rev-parse --abbrev-ref HEAD) != $BRANCH ]; then
			echo
			echo "Try to switch branch"

			git checkout $BRANCH 2>&1
			git checkout -b $BRANCH "origin/$BRANCH" 2>&1

			echo "Git Btanch is: $(git rev-parse --abbrev-ref HEAD)"
		fi

		#Execute special script
		if [ -f "$LOCAL_PATCH/execute.cgi" ]; then
			source "$LOCAL_PATCH/execute.cgi"
		fi

		echo
		echo "Increase version"

		if [ "$(grep "$version" 'version.ini')" ]; then
			RESULT=$(grep "$version" 'version.ini')
			OLD_VERSION=$(echo $RESULT | cut -d'=' -f 2)
			OLD_STRING=$(echo $OLD_VERSION | sed -e 's/\.//g')
			NEW_STRING=$(echo $((OLD_STRING + 1)) | sed 's/.\{1\}/&./g')
			NEW_VERSION="${NEW_STRING%?}"
			
			echo "New version is: $NEW_VERSION"
			sed -i "s/$OLD_VERSION/$NEW_VERSION/" 'version.ini'
		else
			echo 'Create version file'
			echo 'version=0' >> 'version.ini'
		fi

		echo
		echo "Build complete"
		echo "Git Status:"
		echo

		git status

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