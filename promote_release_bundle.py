import os
import requests
import json
import subprocess
import sys

# MODIFIED to correctly handle the repository_key as a query parameter
def get_release_bundle_details(url, access_token, repository_key, release_bundle, bundle_version, project_key):
    """
    Fetches release bundle audit details from Artifactory, specifying the source repository.
    Returns parsed JSON data or None on failure.
    """
    api_url = f"{url}/lifecycle/api/v2/audit/{release_bundle}/{bundle_version}?project={project_key}&repository_key={repository_key}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    print(f"::debug::Querying audit trail: {api_url}")
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        if response.status_code == 404:
            print(f"::notice::Release bundle '{release_bundle}/{bundle_version}' not found at {url}. This may be expected.")
            return None
        response.raise_for_status() # Raise an HTTPError for other bad responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"::error::API request failed to {api_url}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"::error::Failed to decode JSON response from {api_url}: {e}")
        return None

# This function is unchanged from your original
def update_release_bundle_milliseconds(target_url, access_token, release_bundle, bundle_version, promotion_created_millis, project_key="default"):
    """
    Updates release bundle with correct timestamp for a specific promotion record.
    Returns parsed JSON data or None on failure.
    """
    try:
        promotion_created_millis = int(promotion_created_millis) + 1
    except (ValueError, TypeError):
        print(f"::warning::promotion_created_millis '{promotion_created_millis}' is not a valid number. Cannot increment.")
        pass

    api_url = f"{target_url}/lifecycle/api/v2/promotion/records/{release_bundle}/{bundle_version}?project={project_key}&operation=copy&promotion_created_millis={promotion_created_millis}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    print(f"Attempting to update/get promotion record with API: {api_url}")
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"::error::API request failed to {api_url}: {e}")
        return None

# This function is unchanged from your original
def get_release_bundle_names_with_project_keys(source_url, access_token):
    """
    Gets list of release bundles with project key from /lifecycle/api/v2/release_bundle/names.
    Returns parsed JSON data or None on failure.
    """
    api_url = f"{source_url}/lifecycle/api/v2/release_bundle/names"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    print(f"Fetching release bundle names from: {api_url}")
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"::error::API request failed to {api_url}: {e}")
        return None

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

    if not all([source_access_token,target_access_token, source_url, target_url, release_bundle_name, bundle_version, environment, input_repository_key]):
        print("::error::Missing one or more required environment variables.")
        sys.exit(1)

    print(f"Processing bundle: {release_bundle_name}/{bundle_version}")
    print(f"Source JPD: {source_url}")
    print(f"Target JPD: {target_url}")
    print(f"Desired Target Environment: {environment}")
    print(f"Input Repository Key (for project lookup): {input_repository_key}")

    # --- 1. Get Project Key based on repository_key ---
    project_key = "default" 
    names_response = get_release_bundle_names_with_project_keys(source_url, source_access_token)
    if names_response and "release_bundles" in names_response:
        for rb_info in names_response["release_bundles"]:
            if rb_info.get("repository_key") == input_repository_key:
                project_key = rb_info.get("project_key", "default")
                print(f"::notice::Matched repository_key '{input_repository_key}' to project_key '{project_key}'.")
                break
    
    # --- NEW: Pre-flight Check to Prevent Loop ---
    print("\n--- Checking current environment on target Artifactory ---")
    target_audit_data = get_release_bundle_details(target_url, target_access_token, input_repository_key, release_bundle_name, bundle_version, project_key)

    if target_audit_data:
        # The audit trail is newest-first, so the first promotion found is the latest.
        for audit_event in target_audit_data.get("audits", []):
            if audit_event.get("subject_type") == "PROMOTION":
                current_environment = audit_event.get("context", {}).get("environment")
                print(f"::notice::Found most recent promotion on target to environment: '{current_environment}'.")
                if current_environment == environment:
                    print(f"\n✅ Release bundle is already in the target environment '{environment}'.")
                    print("Skipping promotion to prevent a loop. Exiting successfully.")
                    sys.exit(0)
                # Found the latest promotion, no need to look further.
                break
    print("----------------------------------------------------------")

    # --- 2. Get release bundle audit details from SOURCE (Original Logic) ---
    # MODIFIED to use the updated function signature
    audit_data = get_release_bundle_details(source_url, source_access_token, input_repository_key, release_bundle_name, bundle_version, project_key)

    if audit_data is None:
        print("::error::Failed to retrieve audit details from source. Exiting.")
        sys.exit(1)

    # ... The rest of your original script logic continues unchanged ...
    
    promotion_audit_event = None
    audits_list = audit_data.get("audits", [])
    start_index = 0
    if audits_list and audits_list[0].get("subject_type") == "EXTERNAL_EVIDENCE":
        print("::notice::First audit event is EXTERNAL_EVIDENCE, skipping it and checking next.")
        start_index = 1

    for audit_event in audits_list[start_index:]:
        if audit_event.get("subject_type") == "PROMOTION" and audit_event.get("event_status") == "COMPLETED":
            promotion_audit_event = audit_event
            print(f"::notice::Found the first COMPLETED PROMOTION event at index {audits_list.index(audit_event)}.")
            break
    
    if promotion_audit_event is None:
        print("::error::Could not find a COMPLETED PROMOTION event after potential evidence skip. Exiting.")
        sys.exit(1)

    context = promotion_audit_event.get("context", {}) 
    promotion_created_millis = context.get("promotion_created_millis", "0")
    included_repository_keys = context.get("included_repository_keys", [])
    excluded_repository_keys = context.get("excluded_repository_keys", [])

    print("\n--- Extracted Release Bundle Details (from PROMOTION event) ---")
    print(f"Included Repository Keys: {included_repository_keys}")
    print(f"Excluded Repository Keys: {excluded_repository_keys}")
    print(f"Determined Project Key: {project_key}")
    print("----------------------------------------")

    include_repos_param = ""
    if included_repository_keys:
        include_repos_str = ",".join(included_repository_keys)
        include_repos_param = f"--include-repos={include_repos_str}"

    exclude_repos_param = ""
    if excluded_repository_keys:
        exclude_repos_str = ",".join(excluded_repository_keys)
        exclude_repos_param = f"--exclude-repos={exclude_repos_str}"

    jf_rbp_command = [
        "jf", "rbp",
        release_bundle_name,
        bundle_version,
        environment,
        f"--project={project_key}"
    ]

    if include_repos_param:
        jf_rbp_command.append(include_repos_param)
    if exclude_repos_param:
        jf_rbp_command.append(exclude_repos_param) 

    print("\n--- Executing JFrog CLI Command ---")
    print(f"Command: {' '.join(jf_rbp_command)}")

    try:
        result = subprocess.run(jf_rbp_command, check=True, capture_output=True, text=True)
        print("STDOUT:\n", result.stdout)
        print("STDERR:\n", result.stderr)
        print("::notice::Release bundle promotion command executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"::error::Release bundle promotion command failed with exit code {e.returncode}")
        print("STDOUT:\n", e.stdout)
        print("STDERR:\n", e.stderr)
        sys.exit(e.returncode)

    # --- 3. Update release bundle promotion timestamp ---
    updaterbresponse = update_release_bundle_milliseconds(target_url, target_access_token, release_bundle_name, bundle_version, promotion_created_millis, project_key)
    
    if updaterbresponse is None:
        print("::error::Failed to update release bundle promotion timestamp.")
        sys.exit(1)
    else:
        print("\n--- Update Release Bundle Timestamp Response ---")
        print(json.dumps(updaterbresponse, indent=2))
        print("------------------------------------------------")

if __name__ == "__main__":
    main()
