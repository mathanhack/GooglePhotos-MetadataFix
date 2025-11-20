import os
import json
import sys
import logging
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("metadata_update.log"),
        logging.StreamHandler()
    ]
)

# Define supported image extensions
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.mp4', '.mov', '.avi', '.webp'}

# Regex patterns
STEM_REGEX = r'.*\(\d+\)\..*'

def validate_drive_access(path):
    """Validate that the drive/path is accessible and writable."""
    try:
        # Check if path exists and is accessible
        if not os.path.exists(path):
            logging.error(f"Path does not exist: {path}")
            return False
        
        if not os.path.isdir(path):
            logging.error(f"Path is not a directory: {path}")
            return False
        
        # Check if we can read the directory
        try:
            os.listdir(path)
        except PermissionError:
            logging.error(f"Permission denied accessing: {path}")
            return False
        except OSError as e:
            logging.error(f"Drive access error for {path}: {e}")
            return False
        
        # For USB drives, check if it's still mounted by testing write access
        test_file = os.path.join(path, '.metadata_fix_test')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logging.debug(f"Drive access validated for: {path}")
            return True
        except (OSError, IOError) as e:
            logging.warning(f"Drive may be read-only or disconnected: {path} - {e}")
            return False
    
    except Exception as e:
        logging.error(f"Unexpected error validating drive access: {e}")
        return False

def check_drive_during_processing(path):
    """Check if drive is still accessible during processing."""
    try:
        # Quick check - try to access the directory
        os.listdir(path)
        return True
    except (OSError, IOError) as e:
        logging.error(f"Drive became inaccessible during processing: {path} - {e}")
        return False
    """Generate regex to match JSON files with time-based naming pattern."""
    tokens = filename.split(".")
    name = re.escape(".".join(tokens[0:len(tokens) - 1]))
    ext = re.escape(tokens[len(tokens) - 1])
    return fr".*{name}( (\d{{1,2}}\.){{2}}\d{{1,2}} [AP]M)+\.{ext}\..*"

def get_alike_regex_with_duplication(filename):
    """Generate regex to match JSON files with duplication in name."""
    return fr".*{re.escape(filename)}( (\d{{1,2}}\.){{2}}\d{{1,2}} [AP]M)+\..*"

def move_duplication_string(path):
    """Move duplication indicator from middle to end of filename."""
    pattern = r"(.*)\((.*?)\)(\..*)"
    match = re.search(pattern, path)
    if match:
        new_path = match.group(1) + match.group(3) + "(" + match.group(2) + ")"
        return new_path
    else:
        return path

def is_supported_image(filename):
    """Check if the file is a supported image/video type."""
    ext = os.path.splitext(filename.lower())[1]  # Extract extension
    return ext in SUPPORTED_EXTENSIONS and not filename.startswith('.')

def cache_json_files(directory):
    """Pre-cache all JSON files in a directory to avoid repeated directory scans."""
    json_cache = {}
    logging.info(f"Caching JSON files in {directory}...")
    for dirpath, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.endswith('.json'):
                file_path = os.path.join(dirpath, filename)
                json_cache[file_path] = None
    logging.info(f"Cached {len(json_cache)} JSON files")
    return json_cache

def get_alike_json(path, json_files_cache):
    """Find matching JSON file using regex patterns."""
    dir_path = os.path.dirname(path)
    file_name = os.path.basename(path)
    
    # Filter JSON files in the same directory
    jsons = [f for f in json_files_cache.keys() if os.path.dirname(f) == dir_path]
    
    # Try first regex pattern
    regex = get_alike_regex(file_name)
    for json_file in jsons:
        if re.match(regex, json_file):
            return json_file

    # Try with duplication pattern
    file_name = os.path.basename(move_duplication_string(path))
    regex = get_alike_regex_with_duplication(file_name)
    for json_file in jsons:
        if re.match(regex, json_file):
            return json_file
    
    return None

def get_json_data(image_path, json_files_cache):
    """Get JSON data for an image using various fallback methods."""
    # Try direct match with moved duplication string
    json_path = Path(move_duplication_string(image_path) + ".json")
    json_path_str = str(json_path)
    
    if json_path_str in json_files_cache:
        if json_files_cache[json_path_str] is None:
            try:
                with open(json_path, 'r', encoding='utf-8') as f:  # Added encoding
                    json_files_cache[json_path_str] = json.load(f)
            except Exception as e:
                logging.error(f"Error reading {json_path}: {e}")
        return json_files_cache[json_path_str]
    
    # Try direct match
    json_path = Path(image_path + ".json")
    json_path_str = str(json_path)
    
    if json_path_str in json_files_cache:
        if json_files_cache[json_path_str] is None:
            try:
                with open(json_path, 'r', encoding='utf-8') as f:  # Added encoding
                    json_files_cache[json_path_str] = json.load(f)
            except Exception as e:
                logging.error(f"Error reading {json_path}: {e}")
        return json_files_cache[json_path_str]
    
    # Try without "-edited"
    no_edited = image_path.replace("-edited", "")
    json_path = Path(no_edited + ".json")
    json_path_str = str(json_path)
    
    if json_path_str in json_files_cache:
        if json_files_cache[json_path_str] is None:
            try:
                with open(json_path, 'r', encoding='utf-8') as f:  # Added encoding
                    json_files_cache[json_path_str] = json.load(f)
            except Exception as e:
                logging.error(f"Error reading {json_path}: {e}")
        return json_files_cache[json_path_str]
    
    # Try regex matching
    alike_json = get_alike_json(image_path, json_files_cache)
    if alike_json:
        if json_files_cache[alike_json] is None:
            try:
                with open(alike_json, 'r', encoding='utf-8') as f:  # Added encoding
                    json_files_cache[alike_json] = json.load(f)
            except Exception as e:
                logging.error(f"Error reading {alike_json}: {e}")
        return json_files_cache[alike_json]
    
    logging.warning(f"Could not find JSON file for {image_path}")
    return None

def update_image_metadata(args):
    """Update image metadata with timestamp from JSON file."""
    image_path, json_files_cache, dry_run, base_path = args
    
    try:
        # Check if drive is still accessible
        if not check_drive_during_processing(base_path):
            logging.error(f"Drive disconnected, skipping: {image_path}")
            return False
        
        # Get the timestamp from the JSON file
        json_data = get_json_data(image_path, json_files_cache)
        if not json_data:
            return False
        
        if 'photoTakenTime' not in json_data:
            logging.warning(f"No photoTakenTime in JSON for {image_path}")
            return False
            
        timestamp = float(json_data['photoTakenTime']['timestamp'])
        formatted_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        
        if dry_run:
            logging.info(f"Would update {image_path} with timestamp {formatted_time}")
            return True
        
        # Update the image's creation time with retry for USB drives
        max_retries = 3
        for attempt in range(max_retries):
            try:
                os.utime(image_path, (timestamp, timestamp))
                logging.debug(f"Updated {image_path} with timestamp {formatted_time}")
                return True
            except (OSError, IOError) as e:
                if attempt < max_retries - 1:
                    logging.warning(f"Retry {attempt + 1}/{max_retries} for {image_path}: {e}")
                    time.sleep(0.5)  # Brief pause before retry
                else:
                    logging.error(f"Failed to update {image_path} after {max_retries} attempts: {e}")
                    return False
    
    except Exception as e:
        logging.error(f"Error updating metadata for {image_path}: {str(e)}")
        return False

def count_files(path):
    """Count the number of supported files in the directory."""
    count = 0
    for dirpath, _, filenames in os.walk(path):
        for filename in filenames:
            if is_supported_image(filename) and not filename.startswith('.'):
                count += 1
    return count

def process_directory(path, dry_run=False, max_workers=4):
    """Process all supported files in the directory."""
    # Validate drive access first
    if not validate_drive_access(path):
        logging.error(f"Cannot access or write to drive: {path}")
        return 0, 0
    
    # Count files for progress reporting
    total_files = count_files(path)
    logging.info(f"Found {total_files} files to process")
    
    if total_files == 0:
        logging.info("No supported files found to process")
        return 0, 0
    
    # Cache JSON files
    json_files_cache = cache_json_files(path)
    
    # Collect all image files
    image_files = []
    for dirpath, _, filenames in os.walk(path):
        for filename in filenames:
            if not filename.endswith('.json') and filename != '.DS_Store' and is_supported_image(filename):  # Fixed condition
                image_files.append(os.path.join(dirpath, filename))
    
    # Process files in parallel
    processed = 0
    successful = 0
    
    # Adjust thread count for USB drives (reduce for better stability)
    if is_likely_usb_drive(path):
        max_workers = min(max_workers, 2)  # Reduce threads for USB drives
        logging.info(f"Detected possible USB drive, reducing threads to {max_workers}")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create a list of arguments for each file
        args_list = [(file_path, json_files_cache, dry_run, path) for file_path in image_files]
        
        # Process files and track progress
        for result in executor.map(update_image_metadata, args_list):
            processed += 1
            if result:
                successful += 1
            
            # Report progress more frequently for USB drives (every 50 files instead of 100)
            progress_interval = 50 if is_likely_usb_drive(path) else 100
            if processed % progress_interval == 0 or processed == total_files:
                percent = (processed / total_files) * 100 if total_files > 0 else 0
                logging.info(f"Progress: {processed}/{total_files} files processed ({percent:.1f}%)")
    
    logging.info(f"Completed: {successful}/{total_files} files successfully processed")
    return successful, total_files

def is_likely_usb_drive(path):
    """Heuristic to detect if path is likely on a USB drive."""
    try:
        # Check common USB mount points
        usb_indicators = ['/media/', '/mnt/', '/Volumes/']
        path_lower = path.lower()
        
        for indicator in usb_indicators:
            if indicator in path_lower:
                return True
        
        # Check filesystem type or other characteristics
        try:
            import shutil
            total, used, free = shutil.disk_usage(path)
            # Additional check: look for removable media keywords in path
            removable_keywords = ['removable', 'usb', 'external']
            if any(keyword in path_lower for keyword in removable_keywords):
                return True
        except:
            pass
        
        return False
    except:
        return False

def main():
    """Main function to parse arguments and run the script."""
    parser = argparse.ArgumentParser(description='Update image metadata from Google Photos JSON files')
    parser.add_argument('path', help='Directory path containing images and JSON files')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without modifying files')
    parser.add_argument('--threads', type=int, default=4, help='Number of worker threads (default: 4)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Expand path to handle relative paths and resolve symlinks
    args.path = os.path.abspath(os.path.expanduser(args.path))
    
    # Validate path
    if not os.path.exists(args.path):
        logging.error(f"Path does not exist: {args.path}")
        return 1
    
    if not os.path.isdir(args.path):
        logging.error(f"Path is not a directory: {args.path}")
        return 1
    
    # Check if it's likely a USB drive and provide helpful info
    if is_likely_usb_drive(args.path):
        logging.info(f"Processing files on what appears to be a USB/removable drive: {args.path}")
        logging.info("USB drive detected - using optimized settings for better reliability")
    
    logging.info(f"Starting metadata update in {args.path}" + (" (DRY RUN)" if args.dry_run else ""))
    logging.info(f"Using {args.threads} worker threads")
    
    # Process the directory
    successful, total = process_directory(args.path, args.dry_run, args.threads)
    
    # Report results
    if args.dry_run:
        logging.info(f"Dry run completed: Would update {successful} of {total} files")
    else:
        logging.info(f"Update completed: Updated {successful} of {total} files")
    
    return 0 if successful == total else 1

if __name__ == "__main__":
    sys.exit(main())
