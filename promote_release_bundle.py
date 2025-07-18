import os
import requests
import json
import subprocess
import sys


def get_release_bundle_details(target_url, access_token, repository_key, release_bundle, bundle_version, project_key):
    """
    Fetches release bundle audit details from Artifactory.
    """
    api_url = f"{target_url}/lifecycle/api/v2/audit/{release_bundle}/{bundle_version}?project={project_key}&repository_key={repository_key}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    print(f"::debug::Checking audit trail with URL: {api_url}")
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        # A 404 is OK here, it just means the bundle doesn't exist on the target yet
        if response.status_code == 404:
            print("::notice::Release bundle does not exist on target yet. Proceeding with promotion.")
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"::warning::Could not get audit details from target: {e}. Proceeding with promotion.")
        return None

# This function is no longer needed since we are using the JFrog CLI
# def promote_release_bundle_with_property(...)

def main():
    # --- Input parameters from GitHub Actions Environment ---
    target_access_token = os.getenv("TARGET_ACCESS_TOKEN")
    source_url = os.getenv("SOURCE_URL") # Keep for potential future use, but not strictly needed now
    target_url = os.getenv("TARGET_URL")
    release_bundle_name = os.getenv("RELEASE_BUNDLE")
    bundle_version = os.getenv("BUNDLE_VERSION")
    environment = os.getenv("ENVIRONMENT")
    input_repository_key = os.getenv("REPOSITORY_KEY")
    project_key = os.getenv("PROJECT_KEY", "default") # Get project key from env or use default

    if not all([target_access_token, target_url, release_bundle_name, bundle_version, environment, input_repository_key]):
        print("::error::Missing one or more required environment variables.")
        sys.exit(1)

    print(f"Processing bundle: {release_bundle_name}/{bundle_version}")
    print(f"Target JPD: {target_url}")
    print(f"Desired Target Environment: {environment}")

    # --- 1. Pre-flight Check to Prevent Loop ---
    print("\n--- Checking current environment on target Artifactory ---")
    target_audit_data = get_release_bundle_details(target_url, target_access_token, input_repository_key, release_bundle_name, bundle_version, project_key)

    if target_audit_data:
        for audit_event in target_audit_data.get("audits", []):
            if audit_event.get("subject_type") == "PROMOTION":
                current_environment = audit_event.get("context", {}).get("environment")
                print(f"::notice::Found most recent promotion on target to environment: '{current_environment}'.")
                if current_environment == environment:
                    print(f"\n✅ Release bundle is already in the target environment '{environment}'.")
                    print("Skipping promotion to prevent a loop. Exiting successfully.")
                    sys.exit(0)
                # Found the latest promotion, no need to look further
                break

    # --- 2. Construct and Execute jf rbp command ---
    # This uses the JFrog CLI, which is known to work in your environment
    jf_rbp_command = [
        "jf", "rbp",
        release_bundle_name,
        bundle_version,
        environment,
        f"--project={project_key}",
        # Note: jf rbp does not need repo keys, it finds the bundle by name/version/project
    ]

    print("\n--- Executing JFrog CLI Command ---")
    print(f"Command: {' '.join(jf_rbp_command)}")

    try:
        # Before running, ensure the CLI is configured for the TARGET server
        # This assumes your CI environment configures the JFrog CLI to point to the target server
        result = subprocess.run(jf_rbp_command, check=True, capture_output=True, text=True)
        print("STDOUT:\n", result.stdout)
        print("STDERR:\n", result.stderr)
        print("::notice::Release bundle promotion command executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"::error::Release bundle promotion command failed with exit code {e.returncode}")
        print("STDOUT:\n", e.stdout)
        print("STDERR:\n", e.stderr)
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()
