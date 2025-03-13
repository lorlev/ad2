#!/bin/bash

printf "Content-Type: text/plain"
echo
printf "Status: 200 OK"
echo
echo

echo "Processing request in background..."
root_path=$(dirname $(dirname $(readlink -f "$0")))
local_path="$root_path/auto.deploy"

# Read the entire JSON payload from stdin and store it in a temporary file
post_data=$(mktemp)
cat > "$post_data"

# Execute deploy.cgi in the background while passing the request data
nohup bash -c "$local_path/deploy.cgi < '$post_data' > $local_path/deploy.log 2>&1" &

exit 0