#!/bin/bash

notif_big_sep()   { echo "══════════════════════════════════════"; }
notif_small_sep() { echo "──────────────────────────────────────"; }
notif_ts()        { date -u '+%Y-%m-%d %H:%M:%S UTC'; }

notif_kv() {
	printf "<b>%-10s</b> %s\n" "$1" "$2"
}

notif_code() {
	printf "<code>%s</code>" "$1"
}

notif_escape() {
	echo "$1" | sed \
		-e 's/&/\&amp;/g' \
		-e 's/</\&lt;/g' \
		-e 's/>/\&gt;/g'
}

notif_status() {
	case "$1" in
		SUCCEEDED) echo "<b>SUCCEEDED</b>" ;;
		FAILED)    echo "<b>FAILED</b>" ;;
		*)         echo "<b>$1</b>" ;;
	esac
}

notif_deploy_started() {
	notif_send "$(cat <<EOF
<b>DEPLOYMENT STARTED</b>
$(notif_big_sep)

$(notif_kv "Project:" "$(notif_escape "$PROJECT_DOMAIN")")
$(notif_kv "Host:" "$(notif_escape "$(hostname)")")
$(notif_kv "Branch:" "$(notif_escape "$GIT_BRANCH")")
$(notif_kv "Commit:" "$(notif_code "$(notif_escape "$commit_hash")")")
$(notif_kv "Time:" "$(notif_ts)")
EOF
)"
}

notif_codebuild_started() {
	local build_id="$1"
	notif_send "$(cat <<EOF
$(notif_small_sep)
<b>BUILD STARTED</b>

$(notif_kv "Build ID:" "$(notif_code "$(notif_escape "$build_id")")")
$(notif_small_sep)
EOF
)"
}

notif_codebuild_result() {
	local build_id="$1"
	local status="$2"
	local log_url="$3"

	notif_send "$(cat <<EOF
<b>BUILD RESULT</b>

$(notif_kv "Status:" "$(notif_status "$status")")
$(notif_kv "Build ID:" "$(notif_code "$(notif_escape "$build_id")")")
$(notif_kv "Time:" "$(notif_ts)")
$(notif_kv "Log:" "<a href=\"$(notif_escape "$log_url")\">View CodeBuild log</a>")

$(notif_small_sep)
EOF
)"
}

notif_deploy_result() {
	local status="$1"
	local duration="$2"
	local log_url="$3"

	notif_send "$(cat <<EOF
<b>DEPLOYMENT RESULT</b>

$(notif_kv "Status:" "$(notif_status "$status")")
$(notif_kv "Duration:" "${duration}s")
$(notif_kv "Time:" "$(notif_ts)")
$(notif_kv "Log:" "<a href=\"$(notif_escape "$log_url")\">View deploy log</a>")

$(notif_big_sep)
EOF
)"
}