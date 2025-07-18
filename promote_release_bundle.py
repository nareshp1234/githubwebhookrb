import os
import requests
import json
import sys

# This function is unchanged
def get_release_bundle_details(source_url, access_token, repository_key, release_bundle, bundle_version, project_key):
    """
    Fetches release bundle audit details from Artifactory, specifying the source repository.
    Returns parsed JSON data or None on failure.
    """
    # CORRECTED URL: The repository_key is now a query parameter, not part of the path.
    api_url = f"{source_url}/lifecycle/api/v2/audit/{release_bundle}/{bundle_version}?project={project_key}&repository_key={repository_key}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"::error::API request failed to {api_url}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"::error::Response status code: {e.response.status_code}")
            print(f"::error::Response body: {e.response.text}")
        return None
    except json.JSONDecodeError:
        print(f"::error::Failed to decode JSON response from {api_url}")
        return None


# NEW function to replace 'jf rbp'
def promote_release_bundle_with_property(target_url, access_token, release_bundle, bundle_version, environment, project_key, include_repos, exclude_repos):
    """
    Promotes a release bundle using the REST API and adds a special property to prevent loops.
    """
    api_url = f"{target_url}/lifecycle/api/v2/promotion/promote/{release_bundle}/{bundle_version}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "environment": environment,
        "project_key": project_key,
        "included_repository_keys": include_repos,
        "excluded_repository_keys": exclude_repos,
        "promotion_properties": {
            "replication.status": "automated" # This is our special "tag"
        }
    }

    print("\n--- Executing Promotion via REST API ---")
    print(f"API URL: {api_url}")
    print(f"Payload: {json.dumps(payload)}")

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        print("::notice::Release bundle promotion via API executed successfully.")
        print(f"Response: {response.text}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"::error::Release bundle promotion via API failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"::error::Response status code: {e.response.status_code}")
            print(f"::error::Response body: {e.response.text}")
        return False


def main():
    # --- Input parameters from GitHub Actions Environment ---
    source_access_token = os.getenv("SOURCE_ACCESS_TOKEN")
    target_access_token = os.getenv("TARGET_ACCESS_TOKEN")
    source_url = os.getenv("SOURCE_URL")
    target_url = os.getenv("TARGET_URL")
    release_bundle_name = os.getenv("RELEASE_BUNDLE")
    bundle_version = os.getenv("BUNDLE_VERSION")
    environment = os.getenv("ENVIRONMENT")
    input_repository_key = os.getenv("REPOSITORY_KEY")
    # This environment variable is automatically provided by GitHub Actions
    github_event_path = os.getenv("GITHUB_EVENT_PATH")

    if not all([source_access_token, target_access_token, source_url, target_url, release_bundle_name, bundle_version, environment, input_repository_key, github_event_path]):
        print("::error::Missing one or more required environment variables.")
        sys.exit(1)

    # --- 1. Check the webhook payload to prevent loops ---
    print("--- Checking Webhook Trigger Source ---")
    try:
        with open(github_event_path, 'r') as f:
            github_event = json.load(f)
        
        # The payload structure for webhooks sent from Artifactory
        # The actual properties are inside the 'data' key for promotion events
        promotion_props = github_event.get("data", {}).get("properties", {})
        
        if promotion_props.get("replication.status") == "automated":
            print("\n✅ This promotion was triggered by an automated replication.")
            print("Skipping promotion to prevent a loop. Exiting successfully.")
            sys.exit(0)
        else:
            print("::notice::This is a manual promotion. Proceeding.")

    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"::warning::Could not read or parse GitHub event payload at '{github_event_path}': {e}. Proceeding with caution.")
    print("------------------------------------")
    
    # This part is mostly the same, it now just gathers data for the new promotion function
    project_key = "default"
    # Logic to get project_key from repository_key... (omitted for brevity, it is correct in your script)
    # ... Assume project_key is found ...
    
    print(f"Determined Project Key: {project_key}")

    # Get promotion details from the SOURCE to replicate them
    source_audit_data = get_release_bundle_details(source_url, source_access_token, input_repository_key,release_bundle_name, bundle_version, project_key)
    if source_audit_data is None:
        print("::error::Failed to retrieve audit details from source. Exiting.")
        sys.exit(1)

    promotion_audit_event = None
    for event in source_audit_data.get("audits", []):
        if event.get("subject_type") == "PROMOTION" and event.get("event_status") == "COMPLETED":
            promotion_audit_event = event
            break
    
    if not promotion_audit_event:
        print("::error::Could not find a COMPLETED PROMOTION event on source. Exiting.")
        sys.exit(1)
        
    context = promotion_audit_event.get("context", {})
    included_repository_keys = context.get("included_repository_keys", [])
    excluded_repository_keys = context.get("excluded_repository_keys", [])

    # --- 2. Promote the Release Bundle using the new function ---
    success = promote_release_bundle_with_property(
        target_url,
        target_access_token,
        release_bundle_name,
        bundle_version,
        environment,
        project_key,
        included_repository_keys,
        excluded_repository_keys
    )

    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
