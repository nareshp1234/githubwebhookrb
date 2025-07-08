import os
import requests
import json
import subprocess
import sys

def get_release_bundle_details(source_url, access_token, release_bundle, bundle_version):
    """
    Fetches release bundle audit details from Artifactory.
    Returns parsed JSON data or None on failure.
    """
    api_url = f"{source_url}/lifecycle/api/v2/audit/{release_bundle}/{bundle_version}"
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

def update_release_bundle_milliseconds(target_url, access_token, release_bundle, bundle_version,promotion_created_millis):
    """
    Updates release bundle with correct timestamp
    Returns parsed JSON data or None on failure.
    """
    api_url = f"{source_url}/lifecycle/api/v2/audit/{release_bundle}/{bundle_version}"
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

def main():
    # --- Input parameters from GitHub Actions ---
    # These typically come from environment variables or workflow inputs
    # For a GitHub Actions workflow, these would be passed as environment variables to the script.
    
    # Required inputs for the script
    access_token = os.getenv("ACCESS_TOKEN")
    source_url = os.getenv("SOURCE_URL") # This maps to inputs.sourceurl
    target_url = os.getenv("TARGET_URL") # This maps to inputs.targeturl
    release_bundle_name = os.getenv("RELEASE_BUNDLE") # This maps to inputs.release_bundle
    bundle_version = os.getenv("BUNDLE_VERSION") # This maps to inputs.bundle_version
    environment = os.getenv("ENVIRONMENT") # This maps to inputs.environment

    if not all([access_token, source_url, target_url, release_bundle_name, bundle_version, environment]):
        print("::error::Missing one or more required environment variables.")
        print("Ensure ACCESS_TOKEN, SOURCE_URL, TARGET_URL, RELEASE_BUNDLE, BUNDLE_VERSION, ENVIRONMENT are set.")
        sys.exit(1)

    print(f"Fetching details for bundle: {release_bundle_name}/{bundle_version} from {source_url}")

    # 1. Get release bundle details
    audit_data = get_release_bundle_details(source_url, access_token, release_bundle_name, bundle_version)

    if audit_data is None:
        print("::error::Failed to retrieve audit details. Exiting.")
        sys.exit(1)

    # --- Extract required information from audit_data ---
    # Access the first audit item. Handle cases where 'audits' might be empty or missing 'context'.
    first_audit = audit_data.get("audits", [{}])[0] # Default to [{}] if audits is missing/empty
    context = first_audit.get("context", {}) # Default to {} if context is missing

    event_status = first_audit.get("event_status", "N/A")
    promotion_created_millis = context.get("promotion_created_millis", "N/A")
    included_repository_keys = context.get("included_repository_keys", [])
    excluded_repository_keys = context.get("excluded_repository_keys", [])

    print("\n--- Extracted Release Bundle Details ---")
    print(f"Event Status: {event_status}")
    print(f"Promotion Created Millis: {promotion_created_millis}")
    print(f"Included Repository Keys: {included_repository_keys}")
    print(f"Excluded Repository Keys: {excluded_repository_keys}")
    print("----------------------------------------")

    # --- Prepare jf rbp command parameters ---
    include_repos_param = ""
    if included_repository_keys: # Check if list is not empty
        include_repos_str = ",".join(included_repository_keys)
        include_repos_param = f"--include-repos={include_repos_str}"

    exclude_repos_param = ""
    if excluded_repository_keys: # Check if list is not empty
        exclude_repos_str = ",".join(excluded_repository_keys)
        exclude_repos_param = f"--exclude-repos={exclude_repos_str}"

    # --- Construct and Execute jf rbp command ---
    # Assumes JFrog CLI is already set up and authenticated to the target JPD ('target-server')
    # by the 'setup-jfrog-cli' GitHub Action.
    
    # Base command as a list
    jf_rbp_command = [
        "jf", "rbp",
        release_bundle_name,
        bundle_version,
        environment # This is the target environment name   
    ]

    # Add optional parameters if they exist
    if include_repos_param:
        jf_rbp_command.append(include_repos_param)
    if exclude_repos_param:
        jf_rbp_command.append(exclude_repos_param)
    
    # You might need to add --token or similar if target-server auth isn't sufficient
    # Example: jf_rbp_command.append(f"--token={access_token}") # If access_token works for promotion
    
    print("\n--- Executing JFrog CLI Command ---")
    print(f"Command: {' '.join(jf_rbp_command)}")

    try:
        # Execute the command
        # check=True will raise an error if the command returns a non-zero exit code
        # capture_output=True captures stdout and stderr
        result = subprocess.run(jf_rbp_command, check=True, capture_output=True, text=True)
        print("STDOUT:\n", result.stdout)
        print("STDERR:\n", result.stderr)
        print("::notice::Release bundle promotion command executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"::error::Release bundle promotion command failed with exit code {e.returncode}")
        print("STDOUT:\n", e.stdout)
        print("STDERR:\n", e.stderr)
        sys.exit(e.returncode) # Exit with the command's exit code

    # Update release bundle promotion timestamp
    updaterbresponse = update_release_bundle_milliseconds(target_url, access_token, release_bundle_name, bundle_version,promotion_created_millis)
    

if __name__ == "__main__":
    main()
