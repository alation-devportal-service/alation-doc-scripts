import os
from collections import defaultdict

def batch_urls_by_directory(input_file, output_dir, base_prefix):
    """
    Reads a file of URLs and groups them into separate text files based on their
    directory path structure, ensuring batches are evenly distributed and meet size constraints.

    Args:
        input_file (str): The path to the text file containing a list of URLs.
        output_dir (str): The directory where the batched URL files will be saved.
        base_prefix (str): The base URL prefix to strip before determining the group.
    """
    MIN_BATCH_SIZE = 50
    MAX_BATCH_SIZE = 120

    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found. Please run the first script to generate it.")
        return

    os.makedirs(output_dir, exist_ok=True)
    
    # Group URLs by their first-level directory for more substantial initial groups.
    level_1_groups = defaultdict(list)
    total_urls_read = 0
    unprocessed_urls = []

    print(f"Reading URLs from '{input_file}' and grouping by top-level directory...")
    with open(input_file, 'r', encoding='utf-8') as f:
        all_lines = [line.strip() for line in f if line.strip()]
        total_urls_read = len(all_lines)

        for url in all_lines:
            if url.startswith(base_prefix):
                path_suffix = url[len(base_prefix):]
                path_parts = path_suffix.split('/')
                
                if len(path_parts) > 1:
                    # Group by the first directory name (e.g., "DataProductsandMarketplace")
                    group_key = path_parts[0]
                    level_1_groups[group_key].append(url)
                else:
                    level_1_groups["root"].append(url)
            else:
                unprocessed_urls.append(url)

    processed_url_count = total_urls_read - len(unprocessed_urls)
    final_batches = {}
    all_leftover_urls = []

    print("Analyzing groups and creating evenly sized batches...")

    # Process each top-level directory group
    for group_key, urls in level_1_groups.items():
        if len(urls) < MIN_BATCH_SIZE:
            # If a whole group is too small, save its URLs for a combined misc batch
            all_leftover_urls.extend(urls)
            continue
        
        # This group is large enough, let's split it into perfectly sized chunks
        urls_to_split = sorted(urls)
        part_number = 1
        
        while len(urls_to_split) > 0:
            n = len(urls_to_split)
            
            # If the remaining URLs fit in one batch, this is the last chunk for this group
            if n <= MAX_BATCH_SIZE:
                chunk = urls_to_split
                urls_to_split = []
            else:
                # If the remainder after taking a max-sized chunk would be too small,
                # we need to split the current amount more evenly.
                remainder = n - MAX_BATCH_SIZE
                if 0 < remainder < MIN_BATCH_SIZE:
                    # Split into two roughly equal halves instead of one large and one tiny chunk
                    split_point = (n // 2) + (n % 2) # Ensure it's ceiling division
                    chunk = urls_to_split[:split_point]
                    urls_to_split = urls_to_split[split_point:]
                else:
                    # It's safe to take a full-sized chunk
                    chunk = urls_to_split[:MAX_BATCH_SIZE]
                    urls_to_split = urls_to_split[MAX_BATCH_SIZE:]
            
            batch_key = f"{group_key}_part_{part_number}"
            final_batches[batch_key] = chunk
            part_number += 1

    # Now, handle all the leftovers from small groups
    if all_leftover_urls:
        print(f"Processing {len(all_leftover_urls)} leftover URLs into misc batches...")
        misc_urls_to_split = sorted(all_leftover_urls)
        part_number = 1
        
        # Use the same logic, but the very last batch here might be under the minimum size
        while len(misc_urls_to_split) > 0:
            n = len(misc_urls_to_split)
            
            if n <= MAX_BATCH_SIZE:
                 chunk = misc_urls_to_split
                 misc_urls_to_split = []
            else:
                remainder = n - MAX_BATCH_SIZE
                if 0 < remainder < MIN_BATCH_SIZE:
                    split_point = (n // 2) + (n % 2)
                    chunk = misc_urls_to_split[:split_point]
                    misc_urls_to_split = misc_urls_to_split[split_point:]
                else:
                    chunk = misc_urls_to_split[:MAX_BATCH_SIZE]
                    misc_urls_to_split = misc_urls_to_split[MAX_BATCH_SIZE:]

            batch_key = f"misc_batch_part_{part_number}"
            final_batches[batch_key] = chunk
            part_number += 1

    output_url_count = 0
    print(f"\nSaving {len(final_batches)} final URL batches to '{output_dir}' directory...")
    for group_key, urls in final_batches.items():
        filename = group_key.replace('/', '_') + ".txt"
        output_path = os.path.join(output_dir, filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(urls))

        batch_size = len(urls)
        output_url_count += batch_size
        print(f"  - Created '{output_path}' with {batch_size} URLs.")
    
    # Final verification summary
    print("\n--- Verification Summary ---")
    print(f"Total URLs read from '{input_file}': {total_urls_read}")
    if unprocessed_urls:
        print(f"URLs skipped (did not match prefix '{base_prefix}'): {len(unprocessed_urls)}")
    print(f"Total URLs processed: {processed_url_count}")
    print(f"Total URLs written to batches: {output_url_count}")

    if processed_url_count == output_url_count:
        print("✅ Success: All processed URLs have been accounted for and distributed.")
    else:
        print(f"⚠️ Warning: Mismatch found! {processed_url_count - output_url_count} processed URLs are missing.")
    print("--------------------------")
        
    print(f"\nProcess complete.")


def main():
    """
    Main function to run the URL batching process.
    """
    # This should be the output file from your previous script
    input_filename = "page_level_urls.txt"
    
    # The directory where the new batch files will be created
    output_directory = "url_batches"
    
    # The base URL prefix that is common to all URLs
    base_url_prefix = "https://docs.alation.com/en/latest/"
    
    batch_urls_by_directory(input_filename, output_directory, base_url_prefix)


if __name__ == "__main__":
    main()