#!/bin/sh

LoadEnv(){
	# Check .env file exist
	if [ ! -f "$local_path/.env" ]; then
		cp "$local_path/.env.example" "$local_path/.env"
		echo "$(tput setaf 1) .env file was moved from the example file! $(tput sgr 0)"
		echo "$(tput setaf 1) Don't forget to configure the .env file! $(tput sgr 0)"
	fi

	## Clear spaces, tabs, empty lines & comments in config file
	export $(sed "s/ *= */=/g; s/	//g; s/[#].*$//; /^$/d;" "$local_path/.env")
}

SelfUpdate(){
	echo 'Checking for a New Version (Update Check)'
	cd $local_path

	$(git remote update)

	UPSTREAM=${1:-'@{u}'}
	LOCAL=$(git rev-parse '@{0}')
	REMOTE=$(git rev-parse "$UPSTREAM")
	BASE=$(git merge-base '@{0}' "$UPSTREAM")

	if [ $LOCAL = $REMOTE ]; then
		echo "Up-to-date"
	elif [ $LOCAL = $BASE ]; then
		echo "New version available try to update"
		git pull
	elif [ $REMOTE = $BASE ]; then
		echo "Local version is changed!"
	else
		echo "Diverged need to fix"
	fi

	echo
}

SendPushNotification(){
	comment=$(echo $POST | jq -r '.push.changes[].new | select(.name == "'$(echo $GIT_BRANCH)'" and .type == "branch") | .target.message')
	comment=$(echo $comment | sed ':a;s/\\n/<br>/g') #Clear New Lines
	author=$(echo $POST | jq -r '.actor.display_name')
	repository=$(echo $POST | jq -r '.repository.name')
	url=$(echo $POST | jq -r '.push.changes[].new | select(.name == "'$(echo $GIT_BRANCH)'" and .type == "branch") | .target.links.html.href')

	echo
	echo "Send Push Notification "

	message_result=$(curl -s -X GET \
		-H "Content-Type: application/json" \
		"$PUSH_URL?key=$PUSH_SECRET&repository=$repository&branch=$GIT_BRANCH&author=$author&commit=$comment&action_url=$url")

	message_is_send=$(echo $message_result | jq -r '.type')
	if [ "$message_is_send" == "error" ]; then
		echo "Message don't send"
		echo $message_result
	else
		echo "Message send OK"
	fi
}

IncreaseVersion(){
	echo
	echo "Increase version"

	if [ -f "$htdocs_dir/version.ini" ]; then
		result=$(grep "$version" "$htdocs_dir/version.ini")
		old_version=$(echo $result | cut -d'=' -f 2)
		old_string=$(echo $old_version | sed -e 's/\.//g')
		new_string=$(echo $((old_string + 1)) | sed 's/.\{1\}/&./g')
		new_version="${new_string%?}"

		echo "New version is: $new_version"
		sed -i "s/$old_version/$new_version/" "$htdocs_dir/version.ini"
	else
		echo 'Create version file'
		echo 'version=0' >> "$htdocs_dir/version.ini"
	fi
}

FixGitBranch(){
	echo "Git Btanch is: $(git rev-parse --abbrev-ref HEAD)"

	if [ $(git rev-parse --abbrev-ref HEAD) != $GIT_BRANCH ]; then
		echo
		echo "Try to switch branch"

		git checkout $GIT_BRANCH 2>&1
		git checkout -b $GIT_BRANCH "origin/$GIT_BRANCH" 2>&1

		echo "Git Btanch is: $(git rev-parse --abbrev-ref HEAD)"
	fi
}

GetCommitSummary(){
	echo
	echo "Git Status:"
	echo

	git status
}

GetServerSummary(){
	echo
	echo "Your remote address is: ${REMOTE_ADDR}"
	echo "Server time is: $(date)"
	echo "Build complete"
}