#!/bin/bash
# Check for the correct number of arguments

if [ "$#" -ne 5 ]; then
    echo "Usage: $0 <jfrog_url> <access_token> <releasebundle_name> <releasebundle_version> <environment>"
    exit 1
fi

# Assign parameters to variables for clarity
JFROG_URL="${1:?please enter JPD URL. ex - https://workday.jfrog.io}"
ACCESS_TOKEN="${2:?please provide the identity token}"
RELEASEBUNDLE_NAME="${3:?please provide the release bundle name}"
RELEASEBUNDLE_VERSION="${4:?please provide the release bundle version}"
ENVIRONMENT="${5:?please provide the release bundle environment}"

# Rest API to copy artifact from one repo to another
RELEASEBUNDLE_PROMOTION_API_URL="$JFROG_URL/lifecycle/api/v2/promotion/records/$RELEASEBUNDLE_NAME/$RELEASEBUNDLE_VERSION"

# Send the promotion request and capture the response as well as the HTTP status code
RESPONSE=$(curl -s -X POST "$RELEASEBUNDLE_PROMOTION_API_URL" \
-H "Content-Type: application/json" \
-d "{ \"environment\": \"$ENVIRONMENT\",\"included_repository_keys\": [],\"excluded_repository_keys\": [] }" \
-H "Authorization: Bearer $ACCESS_TOKEN")
echo "$RESPONSE"

# Check for success or failure in the response
if echo "$RESPONSE" | jq -e '.messages[] | select(.level == "ERROR")' > /dev/null; then
    # If there are error messages, handle the failure
    echo "Failed to promote Docker image."
    ERROR_MESSAGES=$(echo "$RESPONSE" | jq -r '.messages[] | select(.level == "ERROR") | .message')
    echo "Error details: $ERROR_MESSAGES"
    exit 1 
elif echo "$RESPONSE" | jq -e '.messages[] | select(.level == "INFO")' > /dev/null; then
    # If there are info messages indicating success
    echo "Docker image promotion was successful."
    SUCCESS_MESSAGES=$(echo "$RESPONSE" | jq -r '.messages[] | select(.level == "INFO") | .message')
    echo "Success details: $SUCCESS_MESSAGES"
else
    # If no relevant message is found
    echo "Unexpected response format or no messages found."
    exit 1
fi
