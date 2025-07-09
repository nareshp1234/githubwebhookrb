import os
import requests
import json
import subprocess
import sys

def get_release_bundle_details(source_url, access_token, release_bundle, bundle_version,project_key):
    """
    Fetches release bundle audit details from Artifactory.
    Returns parsed JSON data or None on failure.
    """
    api_url = f"{source_url}/lifecycle/api/v2/audit/{release_bundle}/{bundle_version}?project={project_key}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        
        data = response.json()
        return data
    except requests.exceptions.Timeout:
        print(f"::error::API request timed out to {api_url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"::error::API request failed to {api_url}: {e}")
        if response is not None:
            print(f"::error::Response status code: {response.status_code}")
            print(f"::error::Response body: {response.text}")
        return None
    except json.JSONDecodeError as e:
        print(f"::error::Failed to decode JSON response from {api_url}: {e}")
        if response is not None:
            print(f"::error::Response body: {response.text}")
        return None

def update_release_bundle_milliseconds(target_url, access_token, release_bundle, bundle_version, promotion_created_millis, project_key="default"):
    """
    Updates release bundle with correct timestamp for a specific promotion record.
    Returns parsed JSON data or None on failure.
    """
    # Increment the timestamp as requested, but ensure it's treated as a number
    try:
        promotion_created_millis = int(promotion_created_millis) + 1
    except (ValueError, TypeError):
        print(f"::warning::promotion_created_millis '{promotion_created_millis}' is not a valid number. Cannot increment.")
        # Decide if you want to exit or proceed with original value or a default
        # For now, let's keep it as is if it's not a number, the API might reject it.
        pass

    api_url = f"{target_url}/lifecycle/api/v2/promotion/records/{release_bundle}/{bundle_version}?project={project_key}&operation=copy&promotion_created_millis={promotion_created_millis}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    print(f"Attempting to update/get promotion record with API: {api_url}")

    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        
        data = response.json()
        return data
    except requests.exceptions.Timeout:
        print(f"::error::API request timed out to {api_url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"::error::API request failed to {api_url}: {e}")
        if response is not None:
            print(f"::error::Response status code: {response.status_code}")
            print(f"::error::Response body: {response.text}")
        return None
    except json.JSONDecodeError as e:
        print(f"::error::Failed to decode JSON response from {api_url}: {e}")
        if response is not None:
            print(f"::error::Response body: {response.text}")
        return None

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
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        
        data = response.json()
        return data
    except requests.exceptions.Timeout:
        print(f"::error::API request timed out to {api_url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"::error::API request failed to {api_url}: {e}")
        if response is not None:
            print(f"::error::Response status code: {response.status_code}")
            print(f"::error::Response body: {response.text}")
        return None
    except json.JSONDecodeError as e:
        print(f"::error::Failed to decode JSON response from {api_url}: {e}")
        if response is not None:
            print(f"::error::Response body: {response.text}")
        return None

def main():
    # --- Input parameters from GitHub Actions Environment ---
    # These are passed as environment variables to the Python script by the GitHub Actions workflow.
    access_token = os.getenv("ACCESS_TOKEN")
    source_url = os.getenv("SOURCE_URL")
    target_url = os.getenv("TARGET_URL")
    release_bundle_name = os.getenv("RELEASE_BUNDLE")
    bundle_version = os.getenv("BUNDLE_VERSION")
    environment = os.getenv("ENVIRONMENT")
    # This is the 'repository_key' from the event, used to map to 'project_key'
    input_repository_key = os.getenv("REPOSITORY_KEY") 

    if not all([access_token, source_url, target_url, release_bundle_name, bundle_version, environment, input_repository_key]):
        print("::error::Missing one or more required environment variables.")
        print("Ensure ACCESS_TOKEN, SOURCE_URL, TARGET_URL, RELEASE_BUNDLE, BUNDLE_VERSION, ENVIRONMENT, REPOSITORY_KEY are set.")
        sys.exit(1)

    print(f"Processing bundle: {release_bundle_name}/{bundle_version}")
    print(f"Source JPD: {source_url}")
    print(f"Target JPD: {target_url}")
    print(f"Target Environment: {environment}")
    print(f"Input Repository Key (for project lookup): {input_repository_key}")

    # --- 1. Get Project Key based on repository_key ---
    project_key = "default" # Default to 'default' project if not found or no mapping
    names_response = get_release_bundle_names_with_project_keys(source_url, access_token)

    if names_response and "release_bundles" in names_response:
        for rb_info in names_response["release_bundles"]:
            if rb_info.get("repository_key") == input_repository_key:
                project_key = rb_info.get("project_key", "default")
                print(f"::notice::Matched repository_key '{input_repository_key}' to project_key '{project_key}'.")
                break
        else: # This 'else' belongs to the 'for' loop, executes if loop completes without 'break'
            print(f"::warning::No project_key found for repository_key '{input_repository_key}'. Using default project 'default'.")
    else:
        print("::warning::Could not fetch release bundle names or 'release_bundles' list is empty. Using default project 'default'.")

    # --- 2. Get release bundle audit details ---
    audit_data = get_release_bundle_details(source_url, access_token, release_bundle_name, bundle_version,project_key)

    if audit_data is None:
        print("::error::Failed to retrieve audit details. Exiting.")
        sys.exit(1)

    # --- Extract required information from audit_data ---
    first_audit = audit_data.get("audits", [{}])[0]
    context = first_audit.get("context", {})

    event_status = first_audit.get("event_status", "N/A")
    promotion_created_millis = context.get("promotion_created_millis", "N/A")
    included_repository_keys = context.get("included_repository_keys", [])
    excluded_repository_keys = context.get("excluded_repository_keys", [])

    print("\n--- Extracted Release Bundle Details ---")
    print(f"Event Status: {event_status}")
    print(f"Promotion Created Millis: {promotion_created_millis}")
    print(f"Included Repository Keys: {included_repository_keys}")
    print(f"Excluded Repository Keys: {excluded_repository_keys}")
    print(f"Determined Project Key: {project_key}")
    print("----------------------------------------")

    # --- Prepare jf rbp command parameters ---
    include_repos_param = ""
    if included_repository_keys:
        include_repos_str = ",".join(included_repository_keys)
        include_repos_param = f"--include-repos={include_repos_str}"

    exclude_repos_param = ""
    if excluded_repository_keys:
        exclude_repos_str = ",".join(excluded_repository_keys)
        exclude_repos_param = f"--exclude-repos={exclude_repos_str}"

    # --- Construct and Execute jf rbp command ---
    jf_rbp_command = [
        "jf", "rbp",
        release_bundle_name,
        bundle_version,
        environment, # This is the target environment name
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
    # Call with the determined project_key
    updaterbresponse = update_release_bundle_milliseconds(target_url, access_token, release_bundle_name, bundle_version, promotion_created_millis, project_key)
    
    if updaterbresponse is None:
        print("::error::Failed to update release bundle promotion timestamp.")
        sys.exit(1)
    else:
        print("\n--- Update Release Bundle Timestamp Response ---")
        print(json.dumps(updaterbresponse, indent=2))
        print("------------------------------------------------")


if __name__ == "__main__":
    main()
