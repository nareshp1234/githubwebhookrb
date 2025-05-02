#!/bin/bash
# Check for the correct number of arguments

if [ "$#" -ne 6 ]; then
    echo "Usage: $0 <jfrog_url> <access_token> <source_repo> <target_repo_name> <image_name> <tag>"
    exit 1
fi

# Assign parameters to variables for clarity
JFROG_URL="${1:?please enter JPD URL. ex - https://workday.jfrog.io}"
ACCESS_TOKEN="${2:?please provide the identity token}"
SOURCE_REPO="${3:?please provide the source repository}"
TARGET_REPO="${4:?please provide the target repository}"
IMAGE_NAME="${5:?please provide the image name}"
TAG="$6"

# Check if user has passed tag for docker image, otherwise set it to latest
if [ -z "${TAG}" ]; then
    echo "TAG is set to the empty string. using latest tag"
    TAG="latest"
fi

# Rest API to copy artifact from one repo to another
DOCKER_COPY_API_URL="$JFROG_URL/artifactory/api/copy/$SOURCE_REPO/$IMAGE_NAME/$TAG?to=/$TARGET_REPO/$IMAGE_NAME/$TAG"

# Send the promotion request and capture the response as well as the HTTP status code
RESPONSE=$(curl -s -X POST "$DOCKER_COPY_API_URL" \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $ACCESS_TOKEN")

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
