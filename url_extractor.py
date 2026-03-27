import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse, urlunparse
import concurrent.futures
import os

def get_urls_from_html_sitemap(sitemap_file_path, base_url):
    """
    Finds and returns all URLs from a local HTML sitemap file by parsing <a> tags.
    """
    urls = set()
    print(f"Checking local HTML sitemap: {sitemap_file_path}")
    
    if not os.path.exists(sitemap_file_path):
        print(f"Error: The file '{sitemap_file_path}' was not found.")
        return []

    try:
        with open(sitemap_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, "html.parser")
        
        # Find all <a> tags with an href attribute
        links = soup.find_all("a", href=True)
        for link in links:
            href = link['href']
            # Convert relative URLs (like '/page.html' or '../page.html') to absolute web URLs
            absolute_url = urljoin(base_url, href)
            urls.add(absolute_url)

    except Exception as e:
        print(f"Could not read or parse HTML sitemap {sitemap_file_path}: {e}")
            
    return list(urls)

def check_url_status(url):
    """
    Checks if a URL is active or returns a 404 error.
    Returns the URL and its status ('OK' or '404 Not Found').
    """
    try:
        # Using GET instead of HEAD as some servers don't respond properly to HEAD requests
        response = requests.get(url, allow_redirects=True, timeout=10)
        if response.status_code == 404:
            return url, '404 Not Found'
        return url, 'OK'
    except requests.exceptions.RequestException as e:
        return url, f'Error: {e}'

def main():
    """
    Main function to extract, clean, check URLs, and save them to files.
    """
    # !!! IMPORTANT !!!
    # Please update this path to point to your local sitemap.html file.
    sitemap_file_path = "sitemap.html"  # <--- CHANGE THIS (e.g., "C:/build/sitemap.html" or "./build/sitemap.html")
    
    # Base URL used to construct full URLs from relative links found in the sitemap
    base_url_for_links = "https://docs.alation.com"

    print(f"Starting URL extraction from local sitemap at {sitemap_file_path}...")
    sitemap_urls = get_urls_from_html_sitemap(sitemap_file_path, base_url_for_links)
    
    if not sitemap_urls:
        print("No URLs found in the local sitemap file. Exiting.")
        return

    print("Adding '/en/latest/' to URL paths for validation...")
    urls_to_validate = set()
    for url in sitemap_urls:
        try:
            parsed_url = urlparse(url)
            # Construct the new path, e.g., from '/admins/page.html' to '/en/latest/admins/page.html'
            path_segment = parsed_url.path.lstrip('/')
            new_path = f"/en/latest/{path_segment}"
            
            # Rebuild the URL with the new path
            url_with_version = urlunparse((
                parsed_url.scheme,
                parsed_url.netloc,
                new_path,
                parsed_url.params,
                parsed_url.query,
                parsed_url.fragment
            ))
            urls_to_validate.add(url_with_version)
        except Exception as e:
            print(f"Skipping malformed URL '{url}': {e}")

    # Remove duplicates from the initial list
    unique_urls = sorted(list(urls_to_validate))
    
    print(f"Found {len(unique_urls)} unique URLs. Checking their status. This may take a moment...")
    
    page_level_urls = []
    section_level_urls = []
    error_404_urls = []

    # Using ThreadPoolExecutor to check URLs concurrently for better performance
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_url = {executor.submit(check_url_status, url): url for url in unique_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            try:
                url, status = future.result()
                if status == 'OK':
                    if '#' in url:
                        section_level_urls.append(url)
                        print(f"[SECT OK] {url}")
                    else:
                        page_level_urls.append(url)
                        print(f"[PAGE OK] {url}")
                elif status == '404 Not Found':
                    error_404_urls.append(url)
                    print(f"[ 404  ] {url}")
                else:
                    print(f"[ERROR ] {url} - {status}")
            except Exception as exc:
                print(f'{future_to_url[future]} generated an exception: {exc}')

    # Sort the lists alphabetically
    page_level_urls.sort()
    section_level_urls.sort()
    error_404_urls.sort()

    # Write the results to their respective files
    with open("page_level_urls.txt", "w", encoding="utf-8") as f:
        for url in page_level_urls:
            f.write(url + "\n")
            
    with open("section_level_urls.txt", "w", encoding="utf-8") as f:
        for url in section_level_urls:
            f.write(url + "\n")
            
    with open("404_error_urls.txt", "w", encoding="utf-8") as f:
        for url in error_404_urls:
            f.write(url + "\n")
            
    print("\n--- Process Complete ---")
    print(f"Found {len(page_level_urls)} valid page-level URLs. Saved to page_level_urls.txt")
    print(f"Found {len(section_level_urls)} valid section-level URLs. Saved to section_level_urls.txt")
    print(f"Found {len(error_404_urls)} URLs with 404 errors. Saved to 404_error_urls.txt")

if __name__ == "__main__":
    main()