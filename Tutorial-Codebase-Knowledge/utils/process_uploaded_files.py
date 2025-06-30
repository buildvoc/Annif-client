import os
import fnmatch
# import pathspec # Not directly needed for individual file processing

def process_uploaded_files(
    uploaded_streamlit_files, # Renamed for clarity
    include_patterns=None,
    exclude_patterns=None,
    max_file_size=None,
    upload_directory="input",
):
    """
    Process multiple uploaded files from Streamlit's st.file_uploader.

    Args:
        uploaded_streamlit_files (list): A list of Streamlit UploadedFile objects.
        include_patterns (set): File patterns to include (e.g. {"*.py", "*.js"})
        exclude_patterns (set): File patterns to exclude (e.g. {"tests/*"})
        max_file_size (int): Maximum file size in bytes

    Returns:
        dict: {"files": {filepath: content}}
    """
    files_dict = {}
    total_files = len(uploaded_streamlit_files)
    processed_files_count = 0
    UPLOAD_DIRECTORY  = upload_directory
    os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

    for uploaded_file_obj in uploaded_streamlit_files:
        # Streamlit's UploadedFile object has 'name' and 'read()' methods
        filename = uploaded_file_obj.name

        file_path = os.path.join(UPLOAD_DIRECTORY, filename)

        try:
            file_bytes_content = uploaded_file_obj.getvalue()
            with open(file_path, "wb") as f:
                f.write(file_bytes_content)
            print(f"File '{filename}' saved to '{file_path}'")
        except Exception as e:
            print(f"Error saving '{filename}' to disk: {e}")
            continue
        
        try:
            content = uploaded_file_obj.read().decode("utf-8")
        except UnicodeDecodeError:
            print(f"Warning: Could not decode {filename} as UTF-8. Skipping.")
            processed_files_count += 1
            if total_files > 0:
                percentage = (processed_files_count / total_files) * 100
                rounded_percentage = int(percentage)
                print(f"\033[92mProgress: {processed_files_count}/{total_files} ({rounded_percentage}%) {filename} [skipped (decoding error)]\033[0m")
            continue
        except Exception as e:
            print(f"Warning: Error reading content of {filename}: {e}. Skipping.")
            processed_files_count += 1
            if total_files > 0:
                percentage = (processed_files_count / total_files) * 100
                rounded_percentage = int(percentage)
                print(f"\033[92mProgress: {processed_files_count}/{total_files} ({rounded_percentage}%) {filename} [skipped (read error)]\033[0m")
            continue

        filepath_key = filename # Using the filename as the key, consistent with original

        # Streamlit's UploadedFile object might have a 'size' attribute, but
        # calculating from content directly is safer if you've already read it.
        file_size = len(content.encode("utf-8")) # Get size in bytes

        # --- Exclusion check ---
        excluded = False
        if exclude_patterns:
            for pattern in exclude_patterns:
                if fnmatch.fnmatch(filepath_key, pattern):
                    excluded = True
                    break

        included = False
        if include_patterns:
            for pattern in include_patterns:
                if fnmatch.fnmatch(filepath_key, pattern):
                    included = True
                    break
        else:
            included = True # If no include patterns, all are implicitly included

        processed_files_count += 1
        status = "processed"

        if not included or excluded:
            status = "skipped (excluded)"
            if total_files > 0:
                percentage = (processed_files_count / total_files) * 100
                rounded_percentage = int(percentage)
                print(f"\033[92mProgress: {processed_files_count}/{total_files} ({rounded_percentage}%) {filepath_key} [{status}]\033[0m")
            continue

        if max_file_size and file_size > max_file_size:
            status = "skipped (size limit)"
            if total_files > 0:
                percentage = (processed_files_count / total_files) * 100
                rounded_percentage = int(percentage)
                print(f"\033[92mProgress: {processed_files_count}/{total_files} ({rounded_percentage}%) {filepath_key} [{status}]\033[0m")
            continue

        try:
            files_dict[filepath_key] = content
            # print progress for processed files
            if total_files > 0:
                percentage = (processed_files_count / total_files) * 100
                rounded_percentage = int(percentage)
                print(f"\033[92mProgress: {processed_files_count}/{total_files} ({rounded_percentage}%) {filepath_key} [{status}]\033[0m")
        except Exception as e:
            print(f"Warning: Error adding file {filepath_key} to dictionary: {e}")
            status = "skipped (processing error)"
            if total_files > 0:
                percentage = (processed_files_count / total_files) * 100
                rounded_percentage = int(percentage)
                print(f"\033[92mProgress: {processed_files_count}/{total_files} ({rounded_percentage}%) {filepath_key} [{status}]\033[0m")

    return {"files": files_dict}