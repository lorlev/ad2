#!/bin/bash

# Define paths
root_path=$(dirname $(dirname $(readlink -f "$0")))
local_path="$root_path/auto.deploy"
htdocs_dir="$root_path/htdocs"
logs_dir="$root_path/server.logs"

source "$local_path/inc/functions.cgi"

POST=$(jq '.' < /dev/stdin)
ENV_LOG=$(mktemp)

LoadEnv > "$ENV_LOG" 2>&1

# Detect platform and extract commit details
if [ -n "$HTTP_X_GITLAB_EVENT" ] && [ "$HTTP_X_GITLAB_EVENT" = "Push Hook" ]; then
	platform="gitlab"
	commit_hash=$(echo "$POST" | jq -r '.after')
	repo_url=$(echo "$POST" | jq -r '.repository.git_ssh_url')
elif [ -n "$HTTP_X_EVENT_KEY" ] && [ "$HTTP_X_EVENT_KEY" = "repo:push" ]; then
	platform="bitbucket"
	commit_hash=$(echo "$POST" | jq -r '.push.changes[0].new.target.hash')
	full_name=$(echo "$POST" | jq -r '.repository.full_name')
	repo_url="git@bitbucket.org:${full_name}.git"
elif [ -n "$HTTP_X_GITHUB_EVENT" ] && [ "$HTTP_X_GITHUB_EVENT" = "push" ]; then
	platform="github"
	commit_hash=$(echo "$POST" | jq -r '.after')
	repo_url=$(echo "$POST" | jq -r '.repository.ssh_url')
else
	OutputLog "Unsupported platform"

	SelfUpdate
	exit 1
fi

IS_COMMITS=$(GetCommitsCount "$POST" "$platform")

if [ "$IS_COMMITS" -gt 0 ]; then
	build_dir="$root_path/builds/$commit_hash"

	cat "$ENV_LOG"
	rm -f "$ENV_LOG"

	CloneRepository

	cd "$build_dir"

	if [ -z "$(git config alias.up)" ] || [ "$(git config core.fileMode)" != "false" ]; then
		ModifyGitConfig
	fi

	OutputLog "Git Branch is: $(git rev-parse --abbrev-ref HEAD)"

	if [ "$(git rev-parse --abbrev-ref HEAD)" != "$GIT_BRANCH" ]; then
		CheckoutToBranch
	fi

	BUILDS_COUNT="${BUILDS_COUNT:-3}"

	# Get the commit hash skipping BUILDS_COUNT commits
	old_commit_hash=$(git rev-list --skip="$BUILDS_COUNT" -n 1 "$commit_hash")
	OutputLog "Old commit hash (skipped $BUILDS_COUNT commits): '$old_commit_hash'"

	# Check if the old commit hash is valid and not the same as current
	if [[ -n "$old_commit_hash" ]] && [[ "$commit_hash" != "$old_commit_hash" ]]; then
		OutputLog "Clean Up old build: $old_commit_hash"

		if [[ -d "$root_path/builds/$old_commit_hash" ]]; then
			rm -rf "$root_path/builds/$old_commit_hash" && OutputLog "Old build removed" || OutputLog "Failed to remove old build"
		else
			OutputLog "Build directory does not exist: $root_path/builds/$old_commit_hash"
		fi
	fi

	if [ "$INCREASE_VERSION" == "Y" ] || [ "$INCREASE_VERSION" == "y" ]; then
		IncreaseVersion
	fi

	if [ "$PUSH" == "Y" ] || [ "$PUSH" == "y" ]; then
		SendPushNotification
	fi

	chmod -R 775 "$build_dir"
	chown -R www-data:ftpusers "$build_dir"

	cd "$root_path"

	if [ -n "$STATIC_DIRS" ]; then
		OutputLog "There are static dirs: $STATIC_DIRS"
		CreateSymlinks "dir" "STATIC_DIRS"
		OutputLog ""
	fi

	if [ -n "$STATIC_FILES" ]; then
		OutputLog "There are static files: $STATIC_FILES"
		CreateSymlinks "file" "STATIC_FILES"
		OutputLog ""
	fi

	if [ "$EXECUTE_SCRIPT" == "Y" ] || [ "$EXECUTE_SCRIPT" == "y" ]; then
		cd "$build_dir"

		OutputLog ""
		OutputLog "Execute special ($TECH) script"

		if [ -f "$local_path/tech/$TECH.cgi" ]; then
			source "$local_path/tech/$TECH.cgi"
		fi
	fi

	cd "$root_path"

	if [ -L "$htdocs_dir" ]; then
		OutputLog "Removing existing symlink htdocs"
		rm -f "$htdocs_dir" || OutputLog "Failed to remove symlink"
	elif [ -d "$htdocs_dir" ]; then
		OutputLog "Removing existing directory htdocs."
		rm -rf "$htdocs_dir" || OutputLog "Failed to remove directory"
	fi

	OutputLog "Creating new relative symlink for htdocs"
	ln -s "builds/$commit_hash" "$htdocs_dir" || OutputLog "Failed to create symlink"

	GetCommitSummary
	GetServerSummary

	SelfUpdate
else
	OutputLog "Platform: $platform"
	OutputLog "Commit Hash: $commit_hash"
	OutputLog "Build skipped"

	SelfUpdate
fi