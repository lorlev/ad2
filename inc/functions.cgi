#!/bin/bash

LoadEnv(){
	# Check .env file exist
	if [ ! -f "$local_path/.env" ]; then
		cp "$local_path/.env.example" "$local_path/.env"
		OutputLog "$(tput setaf 1) .env file was moved from the example file! $(tput sgr 0)"
		OutputLog "$(tput setaf 1) Don't forget to configure the .env file! $(tput sgr 0)"
	fi

	## Clear spaces, tabs, empty lines & comments in config file
	export $(sed "s/ *= */=/g; s/	//g; s/[#].*$//; /^$/d;" "$local_path/.env")
}

SelfUpdate() {
	OutputLog 'Checking for a new version (Update Check)'
	cd "$local_path"

	git remote update > /dev/null 2>&1

	UPSTREAM=${1:-'@{u}'}
	LOCAL=$(git rev-parse '@{0}')
	REMOTE=$(git rev-parse "$UPSTREAM")
	BASE=$(git merge-base '@{0}' "$UPSTREAM")

	if [ "$LOCAL" = "$REMOTE" ]; then
		OutputLog "Already up-to-date."
	elif [ "$LOCAL" = "$BASE" ]; then
		OutputLog "New version available. Attempting to update..."

		ERROR_FILE=$(mktemp)

		if git pull > /dev/null 2>>"$ERROR_FILE"; then
			OutputLog "Update successful!"
		else
			OutputLog "Failed to update."
			OutputLog "$(cat "$ERROR_FILE")"
		fi

		rm -f "$ERROR_FILE"
	elif [ "$REMOTE" = "$BASE" ]; then
		OutputLog "Local version has uncommitted changes."
	else
		OutputLog "Branches have diverged. Manual intervention needed."
	fi

	UpdateAccessStructure

	echo
}


UpdateAccessStructure(){
	chmod -R 750 $local_path
	chown -R nginx:sftpusers $local_path

	chmod 400 "$local_path/access/access-key"
	chmod 775 "$local_path/access/access-key.pub"
	chmod 700 "$local_path/index.cgi"
}

ModifyGitConfig(){
	echo
	OutputLog 'Git configuration is not configured'
	OutputLog 'Trying to modify Git configuration'

	#git config alias.get-ignored 'ls-files --others --ignored --exclude-standard'
	#git get-ignored | tr '\n' '\0' | xargs -0r -n1 -I{} cp --parents "{}" ../some_destination/

	git config core.filemode 'false'
	git config alias.up '!git remote update -p; git merge --ff-only @{u}'			#Pull alternative with only fast forward
	git config alias.get-ignored 'ls-files --others --ignored --exclude-standard'	#Get all ignored files
}

SendPushNotification(){
	comment=$(echo $POST | jq -r '.push.changes[].new | select(.name == "'$(echo $GIT_BRANCH)'" and .type == "branch") | .target.message')
	comment=$(echo $comment | sed ':a;s/\\n/<br>/g') #Clear New Lines
	author=$(echo $POST | jq -r '.actor.display_name')
	repository=$(echo $POST | jq -r '.repository.name')
	url=$(echo $POST | jq -r '.push.changes[].new | select(.name == "'$(echo $GIT_BRANCH)'" and .type == "branch") | .target.links.html.href')

	echo
	OutputLog "Send Push Notification"

	message_result=$(curl -s -X GET \
		-H "Content-Type: application/json" \
		"$PUSH_URL?key=$PUSH_SECRET&repository=$repository&branch=$GIT_BRANCH&author=$author&commit=$comment&action_url=$url")

	message_is_send=$(echo $message_result | jq -r '.type')
	if [ "$message_is_send" == "error" ]; then
		OutputLog "Message don't send"
		OutputLog $message_result
	else
		OutputLog "Message send OK"
	fi
}

IncreaseVersion(){
	echo
	OutputLog "Increase version"

	if [ -f "$htdocs_dir/version.ini" ]; then
		result=$(grep "$version" "$htdocs_dir/version.ini")
		old_version=$(echo $result | cut -d'=' -f 2)
		old_string=$(echo $old_version | sed -e 's/\.//g')
		new_string=$(echo $((old_string + 1)) | sed 's/.\{1\}/&./g')
		new_version="${new_string%?}"

		OutputLog "New version is: $new_version"
		sed -i "s/$old_version/$new_version/" "$htdocs_dir/version.ini"
	else
		OutputLog 'Create version file'
		echo 'version=0' >> "$htdocs_dir/version.ini"

		OutputLog "Add to ignored files list"
		echo -n "version.ini" >> "$htdocs_dir/.git/info/exclude"
		echo
	fi
}

FixGitBranch(){
	echo
	OutputLog "Try to switch branch"

	git checkout $GIT_BRANCH 2>&1
	git checkout -b $GIT_BRANCH "origin/$GIT_BRANCH" 2>&1

	OutputLog "Git Btanch is: $(git rev-parse --abbrev-ref HEAD)"
}

GetCommitSummary(){
	echo
	OutputLog "Git Status is:"

	printf -v status_out '%s\n' "$(git -c color.ui=always status)"
	OutputLog "$status_out"
}

GetServerSummary(){
	echo

	OutputLog "Your remote address is: ${REMOTE_ADDR}"
	OutputLog "Server time is: $(date)"
	OutputLog "Build complete"

	OutputLog "--------------------------------------"
}

OutputLog(){
	message=$1

	echo -e "$message"

	if [ ! -d "$logs_dir" ]; then
		mkdir -p "$logs_dir"
	fi

	echo "`date "+%d/%b/%Y:%H:%M:%S %Z"` ""$message" >> "$logs_dir/auto.deploy.log"
}

