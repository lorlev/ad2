#!/bin/bash

OutputLog "Starting build via AWS CodeBuild"

TMP_DIR="/tmp/codebuild-src-$commit_hash"
ZIP_FILE="/tmp/codebuild-src-$commit_hash.zip"
LOG_FILE="$logs_dir/aws.codebuild.log"
CODEBUILD_WAIT_TIMEOUT=${CODEBUILD_WAIT_TIMEOUT:-1800}

BUILD_START_TIME=$(date +%s)

S3_SOURCE_ZIP="s3://${CODEBUILD_S3_BUCKET}/codebuild/sources/${commit_hash}.zip"

FetchCodeBuildLogs() {
	local build_id="$1"
	local log_file="$2"

	LOG_INFO=$(aws codebuild batch-get-builds \
		--ids "$build_id" \
		--query 'builds[0].logs.{group:groupName,stream:streamName}' \
		--output json)

	LOG_GROUP=$(echo "$LOG_INFO" | jq -r '.group')
	LOG_STREAM=$(echo "$LOG_INFO" | jq -r '.stream')

	if [[ -z "$LOG_GROUP" || -z "$LOG_STREAM" || "$LOG_GROUP" == "null" ]]; then
		OutputLog "No CloudWatch logs available"
		return 1
	fi

	aws logs get-log-events \
		--log-group-name "$LOG_GROUP" \
		--log-stream-name "$LOG_STREAM" \
		--start-from-head \
		--query 'events[].message' \
		--output text > "$log_file"
}

OutputLog "Preparing source archive from $build_dir_path"

mkdir -p "$TMP_DIR"

rsync -a \
	--exclude ".git" \
	--exclude "node_modules" \
	--exclude "/vendor" \
	--exclude "storage" \
	--exclude "bootstrap/cache" \
	"$build_dir_path/" "$TMP_DIR/" || {
		OutputLog "ERROR: rsync failed"
		exit 1
	}

cd "$TMP_DIR" || exit 1

zip -qr "$ZIP_FILE" . || {
	OutputLog "ERROR: zip command failed"
	exit 1
}

OutputLog "Uploading source archive to S3: $S3_SOURCE_ZIP"

aws s3 cp "$ZIP_FILE" "$S3_SOURCE_ZIP" \
	--region "$AWS_REGION" || {
		OutputLog "ERROR: Failed to upload source archive to S3"
		exit 1
}

OutputLog "Starting CodeBuild project: $CODEBUILD_PROJECT"

BUILD_ID=$(aws codebuild start-build \
	--project-name "$CODEBUILD_PROJECT" \
	--source-type-override S3 \
	--source-location-override "${CODEBUILD_S3_BUCKET}/codebuild/sources/${commit_hash}.zip" \
	--region "$AWS_REGION" \
	--query 'build.id' \
	--output text)

if [ -z "$BUILD_ID" ] || [ "$BUILD_ID" = "None" ]; then
	OutputLog "ERROR: CodeBuild start-build failed (empty BUILD_ID)"
	exit 1
fi

notif_codebuild_started "$BUILD_ID"

# ---------- WAIT FOR BUILD ----------
while true; do
	STATUS=$(aws codebuild batch-get-builds \
		--ids "$BUILD_ID" \
		--region "$AWS_REGION" \
		--query 'builds[0].buildStatus' \
		--output text)

	if [ -z "$STATUS" ] || [ "$STATUS" = "None" ]; then
		OutputLog "ERROR: Unable to fetch CodeBuild status"
		exit 1
	fi

	OutputLog "Build status: $STATUS"

	case "$STATUS" in
		SUCCEEDED)
			OutputLog "Build completed successfully"

			FetchCodeBuildLogs "$BUILD_ID" "$LOG_FILE"

			CODEBUILD_LOG_URL="$PROJECT_DOMAIN/log.viewer/view/0/aws.codebuild.log"
			notif_codebuild_result "$BUILD_ID" "$STATUS" "$CODEBUILD_LOG_URL"
			break
			;;
		FAILED|FAULT|STOPPED|TIMED_OUT)
			OutputLog "ERROR: Build failed ($STATUS)"

			FetchCodeBuildLogs "$BUILD_ID" "$LOG_FILE"

			CODEBUILD_LOG_URL="$PROJECT_DOMAIN/log.viewer/view/0/aws.codebuild.log"
			notif_codebuild_result "$BUILD_ID" "$STATUS" "$CODEBUILD_LOG_URL"
			exit 1
			;;
	esac

	NOW=$(date +%s)
	if [ $((NOW - BUILD_START_TIME)) -ge "$CODEBUILD_WAIT_TIMEOUT" ]; then
		OutputLog "ERROR: Build timed out after ${CODEBUILD_WAIT_TIMEOUT}s"
		exit 1
	fi

	sleep 20
done

rm -rf "$TMP_DIR" "$ZIP_FILE"

OutputLog "Build CodeBuild stage finished"

OutputLog ""
OutputLog "Downloading build artifacts from S3"

SAFE_BUILD_ID=$(echo "$BUILD_ID" | tr -d '\r\n' | tr ':' '-')
S3_BUILD_PATH="s3://${CODEBUILD_S3_BUCKET}/codebuild/builds/${SAFE_BUILD_ID}"

CLEAN_LOCAL_DIR=$(echo "$build_dir_path/public/build" | tr -d '\r\n ' )

mkdir -p "$CLEAN_LOCAL_DIR"
cd "$CLEAN_LOCAL_DIR" || { OutputLog "ERROR: Cannot cd to $CLEAN_LOCAL_DIR"; exit 1; }

OutputLog "Attempting download to current directory (.)"
CP_OUTPUT=$(aws s3 cp "$S3_BUILD_PATH/" "." \
	--recursive \
	--region "$AWS_REGION" 2>&1)

if [ $? -ne 0 ]; then
	OutputLog "ERROR: s3 cp failed"
	OutputLog "DETAILS: $CP_OUTPUT"
	exit 1
fi

OutputLog "Build artifacts downloaded successfully."
OutputLog ""