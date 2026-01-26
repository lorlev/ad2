#!/bin/bash

# Define paths
root_path=$(dirname $(dirname $(readlink -f "$0")))
local_path="$root_path/auto.deploy"
htdocs_path="$root_path/htdocs"
builds_dir="$root_path/builds"
logs_dir="$root_path/server.logs"
temp_symlink="${htdocs_path}_tmp"

source "$local_path/inc/functions.cgi"
source "$local_path/inc/notifications.cgi"

POST=$(jq '.' < /dev/stdin)
ENV_LOG=$(mktemp)
PROJECT_DOMAIN="$(GetProjectDomain)"

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
	DEPLOY_START_TS=$(date +%s)

	if [ -f "$local_path/notifs/$NOTIF_ENGINE.cgi" ]; then
		source "$local_path/notifs/$NOTIF_ENGINE.cgi"
	fi

	notif_deploy_started

	build_dir_path="$root_path/builds/$commit_hash"

	cat "$ENV_LOG"
	rm -f "$ENV_LOG"

	CloneRepository

	cd "$build_dir_path"

	if [ -z "$(git config alias.up)" ] || [ "$(git config core.fileMode)" != "false" ]; then
		ModifyGitConfig
	fi

	OutputLog "Git Branch is: $(git rev-parse --abbrev-ref HEAD)"

	if [ "$(git rev-parse --abbrev-ref HEAD)" != "$GIT_BRANCH" ]; then
		CheckoutToBranch
	fi

	chmod -R 775 "$build_dir_path"
	chown -R www-data:ftpusers "$build_dir_path"

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

	if [ "$RUN_BUILD" == "Y" ] || [ "$RUN_BUILD" == "y" ]; then
		source "$local_path/builder/$BUILDER.cgi"
	fi

	if [ "$EXECUTE_SCRIPT" == "Y" ] || [ "$EXECUTE_SCRIPT" == "y" ]; then
		cd "$build_dir_path"

		OutputLog "Execute special ($TECH) script"

		if [ -f "$local_path/tech/$TECH.cgi" ]; then
			source "$local_path/tech/$TECH.cgi"
		fi
	fi

	cd "$root_path"

	OutputLog ""
	OutputLog "Creating atomic symlink: $temp_symlink → $build_dir_path"

	ln -sfn "builds/$commit_hash" "$temp_symlink" && OutputLog "Temporary symlink created" || OutputLog "Failed to create temporary symlink"
	mv -T "$temp_symlink" "$htdocs_path" && OutputLog "Symlink atomically switched to new build" || OutputLog "Failed to switch symlink"

	OutputLog "htdocs now points to: $(readlink -f "$htdocs_path")"

	if [ "$INCREASE_VERSION" == "Y" ] || [ "$INCREASE_VERSION" == "y" ]; then
		IncreaseVersion
	fi

	DEPLOY_END_TS=$(date +%s)
	DEPLOY_DURATION=$((DEPLOY_END_TS - DEPLOY_START_TS))

	DEPLOY_LOG_URL="$PROJECT_DOMAIN/log.viewer/view/0/auto.deploy.log"
	notif_deploy_result "SUCCEEDED" "$DEPLOY_DURATION" "$DEPLOY_LOG_URL"

	OutputLog ""
	OutputLog "Cleaning up old builds..."

	BUILDS_COUNT="${BUILDS_COUNT:-3}"

	# List all build directories by modified time, newest first
	build_paths=($(find "$builds_dir" -mindepth 1 -maxdepth 1 -type d -printf "%T@ %p\n" | sort -nr | cut -d' ' -f2-))

	total=${#build_paths[@]}
	if (( total > BUILDS_COUNT )); then
		for ((i=BUILDS_COUNT; i<total; i++)); do
			# Avoid deleting the current build even by mistake
			if [[ "${build_paths[$i]}" != "$build_dir_path" ]]; then
				OutputLog "Removing old build: ${build_paths[$i]}"
				rm -rf "${build_paths[$i]}"
			else
				OutputLog "Skipping removal of current active build: ${build_paths[$i]}"
			fi
		done
	fi

	OutputLog ""

	GetCommitSummary
	GetServerSummary

	SelfUpdate
else
	OutputLog "Platform: $platform"
	OutputLog "Commit Hash: $commit_hash"
	OutputLog "Build skipped"

	SelfUpdate
fi