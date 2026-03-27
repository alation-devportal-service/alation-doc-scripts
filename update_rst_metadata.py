import pandas as pd
import os
import re
import argparse

def get_rst_path_from_url(url, base_path=""):
    """
    Converts a documentation URL to a local .rst file path.

    Args:
        url (str): The full URL from the CSV file.
        base_path (str): The base directory of the documentation source.

    Returns:
        str: The relative file path for the .rst file or None if URL is invalid.
    """
    if not isinstance(url, str):
        return None

    # Define the parts of the URL to strip
    prefix = "https://docs.alation.com/en/latest/"
    suffix = ".html"

    # Clean the URL to get the core path
    if url.startswith(prefix):
        relative_path = url[len(prefix):]
    else:
        # If the prefix doesn't match, we can't determine the path
        print(f"Warning: URL does not have the expected prefix. Skipping URL: {url}")
        return None

    if url.endswith(suffix):
        relative_path = relative_path[:-len(suffix)]
    
    # Construct the final .rst file path
    rst_file = f"{relative_path}.rst"
    
    # Join with the base path if one is provided
    full_path = os.path.join(base_path, rst_file)
    
    return full_path

def add_metadata_to_file(file_path, metadata, force_overwrite=False):
    """
    Adds or overwrites a formatted .. meta:: directive in an .rst file.

    Args:
        file_path (str): The path to the .rst file to be modified.
        metadata (dict): A dictionary containing the metadata to add.
        force_overwrite (bool): If True, overwrites any existing meta directive.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Warning: File not found at '{file_path}'. Skipping.")
        return
    except Exception as e:
        print(f"Error reading file '{file_path}': {e}")
        return

    # --- METADATA BLOCK GENERATION ---
    meta_lines_to_add = []
    
    # Define the order and mapping from the CSV to the directive fields
    field_mapping = {
        'Deployment Type': 'deployment_type',
        'User Role': 'user_role',
        'Functional Area': 'functional_area',
        'Topics': 'topics',
    }

    for csv_key, meta_key in field_mapping.items():
        value = metadata.get(csv_key)
        if pd.notna(value) and str(value).strip():
            # Sanitize the value: replace semicolons and normalize comma spacing.
            sanitized_value_str = str(value).replace(';', ',')
            # Split by comma, strip whitespace from each part, and join with " ; "
            items = [item.strip() for item in sanitized_value_str.split(',') if item.strip()]
            # MODIFIED LINE: Changed separator to a semicolon with spaces.
            final_value = " ; ".join(items)
            # Use three spaces for correct RST indentation instead of a tab.
            meta_lines_to_add.append(f"   :{meta_key}: {final_value}")
            
    # Handle the "Keywords" column
    keywords = metadata.get('Keywords')
    if pd.notna(keywords) and str(keywords).strip():
        # Split by comma, strip whitespace, ensure uniqueness, and re-join
        unique_keywords = sorted(list({k.strip() for k in str(keywords).split(',') if k.strip()}))
        if unique_keywords:
            # Use three spaces for correct RST indentation instead of a tab.
            # MODIFIED LINE: Changed separator to a semicolon with spaces.
            meta_lines_to_add.append(f"   :keywords: {' ; '.join(unique_keywords)}")

    if not meta_lines_to_add:
        print(f"Info: No metadata to add for '{file_path}'. Skipping.")
        return

    # --- CHECK FOR AND HANDLE EXISTING META DIRECTIVE ---
    meta_start_index = -1
    for i, line in enumerate(lines):
        if ".. meta::" in line:
            meta_start_index = i
            break
            
    if meta_start_index != -1:
        if not force_overwrite:
            print(f"Info: '.. meta::' exists in '{file_path}'. Use -f to overwrite. Skipping.")
            return
        else:
            print(f"Info: Found existing '.. meta::' in '{file_path}'. Overwriting due to -f flag.")
            # Find the end of the existing meta block
            meta_end_index = meta_start_index + 1
            while meta_end_index < len(lines):
                line_content = lines[meta_end_index]
                # The block ends when a line has content but is not indented
                if line_content.strip() and not line_content.startswith((' ', '\t')):
                    break
                meta_end_index += 1
            
            # Remove the old block (including any surrounding blank lines handled by insertion)
            del lines[meta_start_index:meta_end_index]
            # Remove the blank line that might have been before the old meta block
            if meta_start_index > 0 and not lines[meta_start_index - 1].strip():
                del lines[meta_start_index - 1]


    # --- FIND INSERTION POINT AND ADD NEW META BLOCK ---
    underline_index = -1
    for i in range(1, len(lines)):
        line_content = lines[i].strip()
        # Only match lines that consist solely of '=' characters.
        if line_content and all(c == '=' for c in line_content):
            # Ensure the line above it (the title) is not blank.
            if lines[i-1].strip():
                underline_index = i
                break
    
    if underline_index == -1:
        print(f"Warning: Could not find a page header underlined with '=' in '{file_path}'. Skipping.")
        return

    # Construct the final block
    full_meta_block = "\n" + ".. meta::\n" + "\n".join(meta_lines_to_add) + "\n\n"
    lines.insert(underline_index + 1, full_meta_block)

    # Write the modified content back to the file
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"Successfully updated metadata in {file_path}")
    except IOError as e:
        print(f"Error: Could not write to file '{file_path}': {e}")


def main():
    """
    Main function to drive the script. Reads a CSV and updates .rst files.
    """
    parser = argparse.ArgumentParser(description="Inject metadata from a CSV file into Sphinx .rst files.")
    parser.add_argument("csv_file", help="The path to the input CSV file.")
    # Add the force overwrite argument
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force overwrite of existing .. meta:: directives in files."
    )
    args = parser.parse_args()

    csv_file = args.csv_file
    
    if not os.path.exists(csv_file):
        print(f"Error: The file '{csv_file}' was not found.")
        return

    print(f"Reading metadata from '{csv_file}'...")
    try:
        # Use the simple, direct pandas reader for standard CSV files.
        # The 'python' engine is more flexible with quotes and delimiters.
        df = pd.read_csv(csv_file, engine='python', index_col=False)

    except Exception as e:
        print(f"Error: Could not parse the CSV file. Please ensure it is formatted correctly. Details: {e}")
        return
        
    if df.empty:
        print("Warning: The CSV file was processed, but no data rows were found. Please check the file content and format.")
        return
    else:
        print(f"Successfully parsed {len(df)} data rows.")
        
    # Clean up column names by stripping any extra whitespace
    df.columns = df.columns.str.strip()
    print(f"Detected columns in CSV: {df.columns.tolist()}")

    # --- Dynamically find the URL column to make the script more robust ---
    url_column_found = None
    possible_url_columns = ['Page URL', 'URL']
    
    for col in df.columns:
        if col in possible_url_columns:
            url_column_found = col
            break

    if not url_column_found:
        print(f"\nError: Could not find a URL column in the CSV.")
        print(f"The script looked for one of these names: {possible_url_columns}")
        return
    
    print(f"Using '{url_column_found}' as the URL column for processing.")
    
    metadata_columns = [
        'Keywords', 'Topics', 'Functional Area', 'User Role', 'Deployment Type'
    ]
    
    doc_base_path = "" 

    print("\nStarting to process .rst files...")
    for index, row in df.iterrows():
        print(f"Processing row {index + 2}/{len(df) + 1}...")
        url = row.get(url_column_found)
        if not url or pd.isna(url):
            print(f"Warning: Skipping row {index + 2} due to missing or invalid URL. Row data: {row.to_dict()}")
            continue

        rst_path = get_rst_path_from_url(url, doc_base_path)
        
        if rst_path:
            metadata = {col: row.get(col) for col in metadata_columns}
            add_metadata_to_file(rst_path, metadata, force_overwrite=args.force)
    
    print("\nProcessing complete.")


if __name__ == "__main__":
    main()
