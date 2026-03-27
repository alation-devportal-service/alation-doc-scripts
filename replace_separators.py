import os
import argparse

def get_rst_path_from_url(url, base_path=""):
    """
    Converts a documentation URL to a local .rst file path.
    This function is reused from the previous script.
    """
    if not isinstance(url, str):
        return None

    prefix = "https://docs.alation.com/en/latest/"
    suffix = ".html"

    if url.startswith(prefix):
        relative_path = url[len(prefix):]
    else:
        print(f"Warning: URL does not have the expected prefix. Skipping URL: {url}")
        return None

    if url.endswith(suffix):
        relative_path = relative_path[:-len(suffix)]
    
    rst_file = f"{relative_path}.rst"
    full_path = os.path.join(base_path, rst_file)
    
    return full_path

def replace_separator_in_meta_block(file_path):
    """
    Finds a .. meta:: block in an .rst file and replaces comma separators
    with semicolon separators in its values.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ Error: File not found at '{file_path}'. Skipping.")
        return
    except Exception as e:
        print(f"❌ Error reading file '{file_path}': {e}")
        return

    meta_start_index = -1
    meta_end_index = -1
    changes_made = False

    # --- Find the start of the meta block ---
    for i, line in enumerate(lines):
        if line.strip() == ".. meta::":
            meta_start_index = i
            break
    
    if meta_start_index == -1:
        print(f"⚠️ Info: No '.. meta::' block found in '{file_path}'. Skipping.")
        return

    # --- Find the end of the meta block ---
    meta_end_index = meta_start_index + 1
    while meta_end_index < len(lines):
        line = lines[meta_end_index]
        # The block ends at the first line that is not empty and not indented
        if line.strip() and not line.startswith((' ', '\t')):
            break
        meta_end_index += 1

    # --- Process each line within the meta block for replacement ---
    for i in range(meta_start_index + 1, meta_end_index):
        line = lines[i]
        # Split the line into key and value, e.g., "   :topics:" and "Value1, Value2"
        parts = line.split(':', 2)
        if len(parts) == 3:
            key_part = parts[0] + ':' + parts[1] + ':'
            value_part = parts[2]
            
            # To robustly handle spacing, we split by comma, strip, and re-join
            if ',' in value_part:
                items = [item.strip() for item in value_part.split(',') if item.strip()]
                new_value_part = " ; ".join(items)
                
                # Reconstruct the line and update it in the list
                lines[i] = key_part + ' ' + new_value_part + '\n'
                changes_made = True

    # --- Write the changes back to the file if any were made ---
    if changes_made:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            print(f"✅ Successfully updated separators in {file_path}")
        except IOError as e:
            print(f"❌ Error: Could not write to file '{file_path}': {e}")
    else:
        print(f"👍 Info: No commas found to replace in the meta block of '{file_path}'. No changes needed.")


def main():
    """
    Main function to drive the script.
    """
    parser = argparse.ArgumentParser(
        description="Replaces comma separators with semicolons in existing .. meta:: blocks of .rst files.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "url_file", 
        help="Path to a text file containing the URLs to process (one URL per line)."
    )
    args = parser.parse_args()

    if not os.path.exists(args.url_file):
        print(f"❌ Error: The input file '{args.url_file}' was not found.")
        return

    print(f"Reading URLs from '{args.url_file}'...")
    with open(args.url_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls:
        print("⚠️ Warning: The URL file is empty. Nothing to process.")
        return

    print(f"\nFound {len(urls)} URLs. Starting to process files...")
    for url in urls:
        rst_path = get_rst_path_from_url(url)
        if rst_path:
            replace_separator_in_meta_block(rst_path)
    
    print("\nProcessing complete.")


if __name__ == "__main__":
    main()
