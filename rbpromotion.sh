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

# Check for success based on the presence of the "created" key
if echo "$RESPONSE" | jq -e '.created' > /dev/null; then
    # If the "created" key is present, it indicates success
    echo "Release bundle promotion was successful."
    SUCCESS_MESSAGES=$(echo "$RESPONSE")
    echo "Success details: $SUCCESS_MESSAGES"
else
    # If the "created" key is not present, check for "errors"
    if echo "$RESPONSE" | jq -e '.errors' > /dev/null; then
        # If the "errors" key is present, output the error details
        echo "Failed to promote the release bundle."
        ERROR_MESSAGES=$(echo "$RESPONSE" | jq -r '.errors[] | .message')
        echo "Error details: $ERROR_MESSAGES"
    else
        # If no known response format is found
        echo "Unexpected response format or no messages found."
    fi
    exit 1
fi
