from pathlib import Path
import sys
import yaml
import subprocess
import shutil
import requests
import os
import logging
from dotenv import load_dotenv
import shutil

# Load .env file
load_dotenv()

# Constants
SCRIPT_DIR = Path(__file__).resolve().parent
ALATION_REPO_PATH = Path.home() / "Developer" / "alation"
SWAGGER_SPECS_PATH = ALATION_REPO_PATH / "django" / "static" / "swagger" / "specs"
LOGICAL_METADATA_PATH = SWAGGER_SPECS_PATH / "logical_metadata"
LOG_FILE = SCRIPT_DIR / "openapi_upload.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

README_API_KEY = os.getenv("README_API_KEY")
README_API_BASE_URL = "https://dash.readme.com/api/v1"

if not README_API_KEY:
    logging.error("README_API_KEY is not set.")
    sys.exit(1)

def pull_latest_alation_repo():
    logging.info("Pulling latest changes from the Alation repository...")
    subprocess.run(["git", "-C", str(ALATION_REPO_PATH), "pull"], check=True)
    logging.info("Repo updated.")

def copy_yaml_file_to_script_dir(filename: str):
    if filename in ["field", "field_value"]:
        source = LOGICAL_METADATA_PATH / f"{filename}.yaml"
    else:
        source = SWAGGER_SPECS_PATH / f"{filename}.yaml"

    if not source.exists():
        logging.error(f"Source YAML file does not exist: {source}")
        sys.exit(1)

    destination = SCRIPT_DIR / source.name
    shutil.copy(source, destination)
    logging.info(f"Copied YAML file to {destination}")

    for folder in ["common", "data_products"]:
        src_folder = SWAGGER_SPECS_PATH / folder
        dest_folder = SCRIPT_DIR / folder
        if dest_folder.exists():
            shutil.rmtree(dest_folder)
        shutil.copytree(src_folder, dest_folder)
        logging.info(f"Copied folder '{folder}' to {dest_folder}")

def check_and_create_version(version: str):
    headers = {
        "Authorization": f"Basic {README_API_KEY}",
        "Accept": "application/json"
    }

    response = requests.get(f"{README_API_BASE_URL}/version", headers=headers)
    if response.status_code != 200:
        logging.error("Failed to fetch ReadMe versions.")
        sys.exit(1)

    if any(v["version"] == version for v in response.json()):
        logging.info(f"Version '{version}' already exists.")
        return

    confirm = input(f"Version '{version}' not found. Create it? (yes/no): ").strip().lower()
    if confirm != "yes":
        logging.info("Exiting without creating version.")
        sys.exit(0)

    payload = {
        "version": version,
        "is_stable": False,
        "from": "latest"
    }

    create_response = requests.post(f"{README_API_BASE_URL}/version", headers=headers, json=payload)
    if create_response.status_code == 201:
        logging.info(f"Version '{version}' created.")
    else:
        logging.error("Error creating version.")
        sys.exit(1)

def read_and_prep_openapi(file_path: Path, version: str):
    with file_path.open("r") as f:
        data = yaml.safe_load(f)

    pos = list(data.keys()).index("openapi")
    items = list(data.items())
    items.insert(pos + 1, ("x-readme", {"explorer-enabled": False}))
    data = dict(items)

    data["info"]["version"] = version
    data["servers"][0]["variables"]["base-url"]["default"] = "alation_domain"
    data["servers"][0]["variables"]["protocol"]["default"] = "https"

    edited_file = file_path.with_name(file_path.stem + "_edited.yaml")
    with edited_file.open("w") as f:
        yaml.dump(data, f, sort_keys=False)

    logging.info(f"Updated YAML written to: {edited_file}")
    return edited_file

def get_api_id(api_name: str, version: str):
    headers = {
        "Authorization": f"Basic {README_API_KEY}",
        "Accept": "application/json",
        "x-readme-version": version
    }

    response = requests.get(f"{README_API_BASE_URL}/api-specification", headers=headers, params={"perPage": 100})
    if response.status_code != 200:
        logging.error("Error retrieving API specs.")
        sys.exit(1)

    for api in response.json():
        if api["title"] == api_name:
            return api["_id"]

    logging.warning(f"No matching API title '{api_name}' found.")
    return None

def validate_with_swagger_cli(file_path: Path):
    logging.info(f"🔍 Validating OpenAPI YAML with Swagger CLI: {file_path}")
    npx_path = shutil.which("npx")
    if not npx_path:
        logging.error("❌ 'npx' was not found in your system PATH.")
        sys.exit(1)
    try:
        subprocess.run(
            [npx_path, "--yes", "swagger-cli", "validate", str(file_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
        logging.info("✅ Swagger CLI validation passed.")
    except subprocess.CalledProcessError as e:
        logging.error("❌ Swagger CLI validation failed.")
        output = e.stderr.strip() or e.stdout.strip() or "Unknown error"
        for line in output.splitlines():
            if "error" in line.lower():
                logging.error(f"• {line.strip()}")
            else:
                logging.warning(f"• {line.strip()}")
        raise RuntimeError("Swagger CLI validation failed")

def validate_with_redocly_cli(file_path: Path):
    logging.info(f"🔍 Validating OpenAPI YAML with Redocly CLI: {file_path}")
    npx_path = shutil.which("npx")
    if not npx_path:
        logging.error("❌ 'npx' was not found in your system PATH.")
        sys.exit(1)
    try:
        process = subprocess.Popen(
            [npx_path, "--yes", "@redocly/cli", "lint", str(file_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8'  # prevent charmap decode error on Windows
        )
        for line in process.stdout:
            clean = line.strip()
            if not clean:
                continue
            if "error" in clean.lower():
                logging.error(clean)
            elif "warning" in clean.lower():
                logging.warning(clean)
            else:
                logging.info(clean)
        process.wait()
        if process.returncode != 0:
            logging.error("❌ Redocly CLI validation failed.")
            sys.exit(process.returncode)
        else:
            logging.info("✅ Redocly CLI validation passed.")
    except Exception as e:
        logging.error(f"Unexpected error during Redocly CLI validation: {e}")
        sys.exit(1)

def upload_to_readme(edited_path: Path, version: str, dry_run=False):
    with edited_path.open("r") as f:
        data = yaml.safe_load(f)
        api_name = data["info"]["title"]

    api_id = get_api_id(api_name, version)

    npx_path = shutil.which("npx")
    if not npx_path:
        logging.error("❌ 'npx' command not found in PATH. Please ensure Node.js is installed.")
        sys.exit(1)

    command = [
        npx_path, "rdme", "openapi", str(edited_path),
        "--useSpecVersion", "--key", README_API_KEY, "--version", version
    ]
    if api_id:
        command.insert(command.index("--key"), "--id")
        command.insert(command.index("--id") + 1, api_id)
    else:
        logging.info("Uploading as new API...")

    logging.info("Upload command: " + " ".join(command))
    if dry_run:
        logging.info("Dry run: skipping upload.")
        return

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8'
        )
        for line in process.stdout:
            clean = line.strip()
            if not clean:
                continue
            if "error" in clean.lower():
                logging.error(clean)
            else:
                logging.info(clean)
        process.wait()

        if process.returncode != 0:
            logging.error(f"❌ rdme upload failed with exit code {process.returncode}")
            sys.exit(process.returncode)
        else:
            logging.info("✅ Upload complete.")

    except Exception as e:
        logging.error(f"❌ Unexpected error while running 'rdme': {e}")
        sys.exit(1)

def main():
    if len(sys.argv) < 3:
        logging.error("Usage: python update_openapi_and_upload.py <filename> <version> [--dry-run] [--local]")
        sys.exit(1)

    input_file = sys.argv[1]
    version = sys.argv[2]
    dry_run = "--dry-run" in sys.argv
    use_local = "--local" in sys.argv

    input_path = SCRIPT_DIR / f"{input_file}.yaml"
    if not use_local:
        pull_latest_alation_repo()
        copy_yaml_file_to_script_dir(input_file)
    else:
        if not input_path.exists():
            logging.error(f"Local file {input_path} not found.")
            sys.exit(1)
        logging.info(f"Using local file: {input_path}")

    check_and_create_version(version)
    edited_path = read_and_prep_openapi(input_path, version)

    if dry_run:
        logging.info("Running in dry-run mode. Choose validation type:")
        logging.info("1. Swagger CLI (OpenAPI 3.0, legacy)")
        logging.info("2. Redocly CLI (OpenAPI 3.1, modern)")
        logging.info("3. Both")
        choice = input("Enter 1, 2, or 3: ").strip()
        if choice == "1":
            try:
                validate_with_swagger_cli(edited_path)
            except RuntimeError:
                pass
        elif choice == "2":
            validate_with_redocly_cli(edited_path)
        elif choice == "3":
            try:
                validate_with_swagger_cli(edited_path)
            except RuntimeError:
                logging.warning("Continuing to Redocly validation despite Swagger failure.")
            validate_with_redocly_cli(edited_path)
        else:
            logging.error("Invalid choice. Exiting.")
            sys.exit(1)

        logging.info("Dry-run completed.")
        return

    upload_to_readme(edited_path, version, dry_run)
    logging.info("Done!")

if __name__ == "__main__":
    main()

