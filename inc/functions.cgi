#!/bin/bash

LoadEnv(){
	# Check .env file exist
	if [ ! -f "$local_path/.env" ]; then
		cp "$local_path/.env.example" "$local_path/.env"

		OutputLog ".env file was moved from the example file!"
		OutputLog "Don't forget to configure the .env file!"
		OutputLog ""
	fi

	OutputLog "Reading .env file:"
	while IFS='=' read -r key value; do
		# Remove leading/trailing whitespace from key and value
		key=$(echo "$key" | sed 's/^[ \t]*//; s/[ \t]*$//')
		value=$(echo "$value" | sed 's/^[ \t]*//; s/[ \t]*$//')

		# Skip empty lines and comments
		if [[ -z "$key" || "$key" == \#* ]]; then
			continue
		fi

		# Remove inline comments from the value
		value=$(echo "$value" | sed 's/[ \t]*#.*$//')

		# Export the variable
		export "$key=$value"
	done < "$local_path/.env"
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

		# Discard any local changes before pulling updates
		git reset --hard HEAD > /dev/null 2>>"$ERROR_FILE"
		git clean -fd > /dev/null 2>>"$ERROR_FILE"
		git pull --rebase > /dev/null 2>>"$ERROR_FILE" || true

		if [ -s "$ERROR_FILE" ]; then
			OutputLog "Failed to update, but continuing execution..."
			OutputLog "$(cat "$ERROR_FILE")"
		else
			OutputLog "Update successful!"
		fi

		rm -f "$ERROR_FILE"
	elif [ "$REMOTE" = "$BASE" ]; then
		OutputLog "Local version has uncommitted changes. Ignoring and continuing..."
		git reset --hard HEAD > /dev/null 2>&1
		git clean -fd > /dev/null 2>&1
		git pull --rebase > /dev/null 2>&1
	else
		OutputLog "Branches have diverged. Resetting local changes and forcing update..."
		git fetch --all > /dev/null 2>&1
		git reset --hard "$UPSTREAM" > /dev/null 2>&1
		git clean -fd > /dev/null 2>&1
	fi

	UpdateAccessStructure
	OutputLog ""
}

UpdateAccessStructure(){
	chmod -R 750 $local_path
	chown -R www-data:ftpusers $local_path

	chmod 400 "$local_path/access/access-key"
	chmod 775 "$local_path/access/access-key.pub"
	chmod 700 "$local_path/index.cgi"
}

GetCommitsCount() {
	local post_payload=$1
	local platform=$2
	local branch=$3

	case $platform in
		"gitlab")
			# GitLab logic
			echo $(echo $post_payload | jq --arg branch "$branch" '[.commits[] | select(.id != null)] | length')
			;;
		"bitbucket")
			# Bitbucket logic
			echo $(echo "$post_payload" | jq '[.push.changes[].new | select(.name == "'$(echo $branch)'" and .type == "branch")] | length')
			;;
		"github")
			# GitHub logic
			echo $(echo $post_payload | jq --arg branch "$branch" '[.commits[] | select(.distinct == true and (.message | length) > 0)] | length')
			;;
		*)
			echo 0
			;;
	esac
}

ModifyGitConfig(){
	OutputLog ""
	OutputLog 'Git configuration is not configured globally'
	OutputLog 'Trying to modify local Git configuration'

	# Set core.fileMode to ignore file permission changes
	git config core.filemode 'false'

	# Set a custom alias "up" for updating and merging with only fast-forward
	git config alias.up '!git remote update -p; git merge --ff-only @{u}'

	# Set a custom alias "get-ignored" to list all ignored files
	git config alias.get-ignored 'ls-files --others --ignored --exclude-standard'
	OutputLog ""
}

SendPushNotification() {
	comment=""
	author=""
	repository=""
	url=""

	case "$platform" in
		"bitbucket")
			# Bitbucket-specific logic
			comment=$(echo $POST | jq -r '.push.changes[].new | select(.name == "'$GIT_BRANCH'" and .type == "branch") | .target.message')
			author=$(echo $POST | jq -r '.actor.display_name')
			repository=$(echo $POST | jq -r '.repository.name')
			url=$(echo $POST | jq -r '.push.changes[].new | select(.name == "'$GIT_BRANCH'" and .type == "branch") | .target.links.html.href')
			;;
		
		"github")
			# GitHub-specific logic
			comment=$(echo $POST | jq -r '.head_commit.message')
			author=$(echo $POST | jq -r '.pusher.name')
			repository=$(echo $POST | jq -r '.repository.name')
			url=$(echo $POST | jq -r '.head_commit.url')
			;;
		
		"gitlab")
			# GitLab-specific logic
			comment=$(echo $POST | jq -r '.commits[0].message')
			author=$(echo $POST | jq -r '.user_name')
			repository=$(echo $POST | jq -r '.repository.name')
			url=$(echo $POST | jq -r '.commits[0].url')
			;;
		
		*)
			OutputLog "Unknown platform: $platform"
			return
			;;
	esac

	# Clear New Lines in the comment
	comment=$(echo $comment | sed ':a;s/\\n/<br>/g')

	OutputLog ""
	OutputLog "Send Push Notification"

	# Send the push notification
	message_result=$(curl -s -X GET \
		-H "Content-Type: application/json" \
		"$PUSH_URL?key=$PUSH_SECRET&repository=$repository&branch=$GIT_BRANCH&author=$author&commit=$comment&action_url=$url")

	# Check if the message was sent successfully
	message_is_send=$(echo $message_result | jq -r '.type')
	if [ "$message_is_send" == "error" ]; then
		OutputLog "Message not sent"
		OutputLog "$message_result"
	else
		OutputLog "Message sent successfully"
	fi
}

IncreaseVersion(){
	OutputLog ""
	OutputLog "Increase version"

	if [ -f "$root_path/static/version.ini" ]; then
		result=$(grep "$version" "$root_path/static/version.ini")
		old_version=$(echo $result | cut -d'=' -f 2)
		old_string=$(echo $old_version | sed -e 's/\.//g')
		new_string=$(echo $((old_string + 1)) | sed 's/.\{1\}/&./g')
		new_version="${new_string%?}"

		OutputLog "New version is: $new_version"
		sed -i "s/$old_version/$new_version/" "$root_path/static/version.ini"
	else
		OutputLog 'Create version file'
		echo 'version=0' >> "$root_path/static/version.ini"

		OutputLog "Add to ignored files list"
		echo -n "version.ini" >> "$root_path/static/.git/info/exclude"
		OutputLog ""
	fi
}

CloneRepository(){
	umask 002

	eval `ssh-agent` &>/dev/null

	OutputLog "Adding SSH key..."
	if ssh-add "$local_path/access/access-key" > /dev/null 2>&1; then
		OutputLog "SSH key added successfully."
	else
		OutputLog "Failed to add SSH key."
	fi

	# Check if the build directory exists, remove if it does, and log the action
	if [ -d "$build_dir" ]; then
		OutputLog ""
		OutputLog "Directory $build_dir exists. Removing existing directory..."
		rm -rf "$build_dir"
		OutputLog "Existing directory removed."
		OutputLog ""
	fi

	# Clone with a depth of 5 commits for the specified branch
	OutputLog "Cloning repository branch $GIT_BRANCH from $repo_url to $build_dir with depth 5"
	if ! git clone --branch "$GIT_BRANCH" --single-branch --depth 5 "$repo_url" "$build_dir" 2> /tmp/git_error.log; then
		OutputLog "Git clone failed. Reason: $(cat /tmp/git_error.log)"
		exit 1
	fi

	OutputLog "Repository cloned successfully with depth 5."

	chown -R www-data:ftpusers "$build_dir"
	chmod -R 775 "$build_dir"

	eval `ssh-agent -k` &>/dev/null

	umask 0022
}

CheckoutToBranch(){
	OutputLog "Try to switch branch"

	git checkout -b $GIT_BRANCH "origin/$GIT_BRANCH" 2>&1

	OutputLog "Git Btanch is: $(git rev-parse --abbrev-ref HEAD)"
	OutputLog ""
}

GetCommitSummary(){
	OutputLog "Git commit hash: $commit_hash"
	OutputLog "Your platform is: ${platform}"
	OutputLog "Git Status is:"

	printf -v status_out '%s\n' "$(git -C "$build_dir" -c color.ui=always status)"
	OutputLog "$status_out"
}

GetServerSummary(){
	OutputLog "The current user is: $(whoami)"
	OutputLog "Your current group is: $(id -gn)"
	OutputLog "Your remote address is: ${REMOTE_ADDR}"
	OutputLog "Server time is: $(date)"
	OutputLog ""

	OutputLog "Build complete"

	OutputLog "--------------------------------------"
	OutputLog ""
}

CreateSymlinks() {
	local type="$1"  # 'file' or 'dir'
	local paths_var="$2"

	local paths="${!paths_var}"

	read -ra ITEMS <<< "$paths"
	for item in "${ITEMS[@]}"; do
		# Determine the source path based on type
		if [ "$type" == "dir" ]; then
			# Ensure the static directory exists
			if [ ! -d "$root_path/static/$item" ]; then
				mkdir -p "$root_path/static/$item"
				OutputLog "Created Static dir: $item"
			fi
			src_path="$root_path/static/$item"
		else
			# Ensure the static file exists
			if [ ! -f "$root_path/static/$item" ]; then
				OutputLog "Static file not found: $item"
				continue
			fi
			src_path="$root_path/static/$item"
		fi

		# Calculate the full path for the symlink in the build directory
		symlink_path="$build_dir/$item"

		# Get the parent directory of the symlink path
		parent_dir=$(dirname "$symlink_path")

		# Create parent directories in the build directory if they don't exist
		if [ ! -d "$parent_dir" ]; then
			mkdir -p "$parent_dir"
			OutputLog "Created parent directory: ${parent_dir#$build_dir/}"
		fi

		# Remove any existing file or symlink at the symlink path
		rm -f "$symlink_path"

		# Calculate the relative path from the symlink location to the source path
		rel_path=$(realpath --relative-to="$parent_dir" "$src_path")

		# Create the symlink
		ln -s "$rel_path" "$symlink_path"

		chmod -R 775 "$rel_path"
		chmod -R 775 "$symlink_path"
		chown -R www-data:ftpusers "$rel_path"
		chown -R www-data:ftpusers "$symlink_path"

		OutputLog "Created symlink for: $item"
	done
}

OutputLog(){
	message=$1

	echo -e "$message"

	if [ ! -d "$logs_dir" ]; then
		mkdir -p "$logs_dir"
	fi

	echo "`date "+%d/%b/%Y:%H:%M:%S %Z"` $message" >> "$logs_dir/auto.deploy.log"
}