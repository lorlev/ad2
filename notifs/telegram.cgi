#!/bin/bash

TG_TOKEN="${NOTIF_TOKEN}"
TG_CHAT="${NOTIF_ID}"

notif_send() {
	if [ "$NOTIF" == "Y" ] || [ "$NOTIF" == "y" ]; then
		local text="$1"

		[ -z "$TG_TOKEN" ] || [ -z "$TG_CHAT" ] && return 0

		curl -s -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
			-d chat_id="${TG_CHAT}" \
			-d parse_mode="HTML" \
			-d disable_web_page_preview=true \
			-d text="$text" >/dev/null
	fi
}