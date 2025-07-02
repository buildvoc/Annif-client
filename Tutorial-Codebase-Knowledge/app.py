import streamlit as st
import os
import dotenv
import tempfile
import json
import time
from flow import create_tutorial_flow
from utils.markdown_converter import markdown_to_html, markdown_to_pdf, create_combined_markdown, get_file_contents
from urllib.parse import urlparse

# Load environment variables
dotenv.load_dotenv()

# Default file patterns
DEFAULT_INCLUDE_PATTERNS = {
    "*.py", "*.js", "*.ts", "*.go", "*.java", "*.pyi", "*.pyx", 
    "*.c", "*.cc", "*.cpp", "*.h", "*.md", "*.rst", "Dockerfile", 
    "Makefile", "*.yaml", "*.yml"
}

DEFAULT_EXCLUDE_PATTERNS = {
    "*test*", "tests/*", "docs/*", "examples/*", "v1/*", 
    "dist/*", "build/*", "experimental/*", "deprecated/*", 
    "legacy/*", ".git/*", ".github/*"
}

# Set page config
st.set_page_config(
    page_title="Codebase Tutorial Generator",
    page_icon="📚",
    layout="wide"
)

# Title and description
st.title("📚 Codebase Tutorial Generator")
st.markdown("""
This app generates comprehensive tutorials for codebases using AI.
Simply provide a GitHub repository URL and customize the generation settings. You can also uploading your files or entering local directory. Local directory crawling only available on localhost.
""")

github_token = None
repo_url = None
input_dir = None
files = None
local_path_dir = None

if "file_source_radio" not in st.session_state:
    st.session_state.file_source_radio = "From Github URL"
    st.session_state.progress_bar = 0

def is_localhost_or_127_0_0_1():
    """
    Checks if the host of a given URL is 'localhost' or '127.0.0.1'.
    """
    if st.context.url:
        parsed_url = urlparse(st.context.url)
        return parsed_url.hostname in ["localhost", "127.0.0.1"]
    return False
# Sidebar for configuration
with st.sidebar:
    st.header("Configuration")

    # GitHub token input
    if st.session_state.file_source_radio == "From Github URL":
        github_token = st.text_input(
            "GitHub Token (optional)", 
            value=os.environ.get("GITHUB_TOKEN", ""),
            type="password",
            help="Personal access token for GitHub API. Helps avoid rate limits."
        )

    # Output directory
    output_dir = st.text_input(
        "Output Directory", 
        value="output",
        help="Directory where the tutorial will be saved"
    )

    # Advanced options
    with st.expander("Advanced Options"):
        # File size limit
        max_file_size = st.number_input(
            "Max File Size (bytes)", 
            value=100000,
            min_value=1000,
            help="Maximum file size to process (in bytes)"
        )

        # Include patterns
        include_patterns_str = st.text_area(
            "Include Patterns", 
            value="\n".join(DEFAULT_INCLUDE_PATTERNS),
            help="File patterns to include (one per line)"
        )

        # Exclude patterns
        exclude_patterns_str = st.text_area(
            "Exclude Patterns", 
            value="\n".join(DEFAULT_EXCLUDE_PATTERNS),
            help="File patterns to exclude (one per line)"
        )

    # Input directory
    if st.session_state.file_source_radio == "Upload files":
        input_dir = st.text_input(
            "Input Directory", 
            value="input",
            help="Input directory where the uploaded files will be saved",
            disabled=st.session_state.file_source_radio != "Upload files",
        )

file_source = st.radio(
    "Files source",
    ["From Github URL", "Upload files", "Local directory"] if is_localhost_or_127_0_0_1 else ["From Github URL", "Upload files"],
    captions=[
        "Files source by entering Github repository URL",
        "Upload one or more files by you",
        "Crawl local directory (available on localhost)",
    ],
    horizontal=True,
    key="file_source_radio"
)
# Main form
with st.form("tutorial_form"):
    # Repository URL
    if st.session_state.file_source_radio == "From Github URL":
        repo_url = st.text_input(
            "GitHub Repository URL",
            placeholder="https://github.com/username/repository",
            help="URL of the public GitHub repository",
            key="repo_url",
            disabled=st.session_state.file_source_radio != "From Github URL",
        )

    if st.session_state.file_source_radio == "Upload files":
        files = st.file_uploader(
            "Upload files",
            help="Ensure files extension are included and not excluded by Advanced Options!",
            accept_multiple_files=True,
            disabled=st.session_state.file_source_radio != "Upload files",
        )
    
    if st.session_state.file_source_radio == "Local directory":
        local_path_dir = st.text_input(
            "Local Directory Path", 
            placeholder="input/path_to_your_codebase",
            help="Crawl local directory (starting with /input directory)",
            disabled=st.session_state.file_source_radio != "Local directory",
        )

    # Project name
    project_name = st.text_input(
        "Project Name",
        help="Name for the project"
    )

    # Submit button
    submit_button = st.form_submit_button("Generate Tutorial", disabled=st.session_state.progress_bar not in [0, 100])

# Process form submission
if submit_button:
    if file_source == "From Github URL" and not repo_url:
        st.error("Please enter a GitHub repository URL")
    elif file_source == "Upload files" and not files:
        st.error("Please select one or more file(s)")
    elif file_source == "Local directory" and not local_path_dir:
        st.error("Please enter Local Directory Path")
    elif not project_name:
        st.error("Please enter project name")
    else:
        # Show progress
        progress_bar = st.progress(1)
        status_text = st.empty()

        # Parse include/exclude patterns
        include_patterns = set(filter(None, include_patterns_str.split("\n")))
        exclude_patterns = set(filter(None, exclude_patterns_str.split("\n")))

        # Initialize shared dictionary
        shared = {
            "repo_url": repo_url if file_source == "From Github URL" else None,
            "project_name": project_name if project_name else None,
            "github_token": github_token if github_token else os.environ.get("GITHUB_TOKEN"),
            "input_dir": input_dir if input_dir else "input",
            "output_dir": output_dir if output_dir else "output",
            "local_dir": local_path_dir if file_source == "Local directory" else None,
            "include_patterns": include_patterns,
            "exclude_patterns": exclude_patterns,
            "max_file_size": max_file_size,
            "input_files": files if file_source == "Upload files" else [],
            "files": [],
            "abstractions": [],
            "relationships": {},
            "chapter_order": [],
            "chapters": [],
            "final_output_dir": None
        }

        try:
            # Create and run the flow
            status_text.text("Starting tutorial generation...")
            progress_bar.progress(10)

            tutorial_flow = create_tutorial_flow()

            # Update status for each node
            status_text.text("Fetching repository...")
            progress_bar.progress(20)

            # Run the flow with progress updates
            # Note: In a real implementation, you would need to modify the flow
            # to provide progress updates or use callbacks
            try:
                result = tutorial_flow.run(shared)

                progress_bar.progress(100)
                status_text.text("Tutorial generation complete!")

                # Display result
                if result and result.get("final_output_dir"):
                    output_dir = result["final_output_dir"]
                    st.success(f"Tutorial generated successfully in: {output_dir}")

                    # Check if output directory exists
                    if os.path.exists(output_dir) and os.path.isdir(output_dir):
                        st.markdown("### Tutorial Content")
                        files = sorted(os.listdir(output_dir))
                        if files:
                            # Create tabs for each file plus a "Complete Tutorial" tab
                            tab_names = [f.replace('.md', '') for f in files]
                            tab_names.append("Complete Tutorial")
                            tabs = st.tabs(tab_names)

                            # Prepare combined content for the complete tutorial
                            combined_content = ""
                            file_contents = {}

                            # First, read all file contents
                            for file in files:
                                file_path = os.path.join(output_dir, file)
                                if os.path.isfile(file_path) and file.endswith('.md'):
                                    try:
                                        with open(file_path, "r", encoding="utf-8") as f:
                                            file_contents[file] = f.read()
                                    except Exception as e:
                                        file_contents[file] = f"Error reading file: {str(e)}"

                            # Process individual tabs
                            for i, file in enumerate(files):
                                if file in file_contents:
                                    content = file_contents[file]

                                    # Display the content in the corresponding tab
                                    with tabs[i]:
                                        # Add download button at the top
                                        with open(os.path.join(output_dir, file), "rb") as f:
                                            st.download_button(
                                                label=f"Download {file}",
                                                data=f,
                                                file_name=file,
                                                mime="text/markdown"
                                            )

                                        # Display the markdown content
                                        st.markdown(content)

                            # Create combined content using our utility function
                            combined_content, combined_file_path = create_combined_markdown(
                                file_contents, 
                                os.path.join(output_dir, "complete_tutorial.md")
                            )

                            # Display the complete tutorial tab
                            with tabs[-1]:
                                if combined_content and combined_file_path:
                                    # Add download buttons for markdown
                                    with open(combined_file_path, "rb") as f:
                                        st.download_button(
                                            label="Download Complete Tutorial (Markdown)",
                                            data=f,
                                            file_name="complete_tutorial.md",
                                            mime="text/markdown"
                                        )

                                    # Convert to HTML for better rendering
                                    html_content = markdown_to_html(combined_content)
                                    if html_content:
                                        # Save HTML file
                                        html_file_path = os.path.join(output_dir, "complete_tutorial.html")
                                        with open(html_file_path, "w", encoding="utf-8") as f:
                                            f.write(html_content)

                                        # Add download button for HTML
                                        with open(html_file_path, "rb") as f:
                                            st.download_button(
                                                label="Download Complete Tutorial (HTML)",
                                                data=f,
                                                file_name="complete_tutorial.html",
                                                mime="text/html"
                                            )

                                    # Convert to PDF and add PDF download button
                                    try:
                                        with st.spinner("Converting to PDF..."):
                                            # Create a file for the PDF
                                            pdf_file_path = os.path.join(output_dir, "complete_tutorial.pdf")

                                            # Convert markdown to PDF
                                            pdf_path = markdown_to_pdf(combined_content, pdf_file_path)

                                            if pdf_path and os.path.exists(pdf_path):
                                                with open(pdf_path, "rb") as f:
                                                    st.download_button(
                                                        label="Download Complete Tutorial (PDF)",
                                                        data=f,
                                                        file_name="complete_tutorial.pdf",
                                                        mime="application/pdf"
                                                    )
                                            else:
                                                st.warning("PDF conversion failed. Please download the HTML or markdown version instead.")
                                    except Exception as e:
                                        st.warning(f"PDF conversion failed: {str(e)}. Please download the HTML or markdown version instead.")

                                    # Display the combined content with proper rendering
                                    st.markdown("## Complete Tutorial")
                                    st.markdown("This tab shows all chapters combined into a single document.")

                                    # Use HTML display for better rendering of Mermaid diagrams
                                    if html_content:
                                        st.components.v1.html(html_content, height=800, scrolling=True)
                                    else:
                                        # Fallback to regular markdown display
                                        st.markdown(combined_content)
                                else:
                                    st.error("Failed to create combined tutorial content.")
                        else:
                            st.info("No files found in the output directory.")
                    else:
                        # If the directory doesn't exist, try to find it in the output base directory
                        output_base_dir = shared.get("output_dir", "output")
                        project_name = shared.get("project_name", "")

                        # Try to find the project directory in the output base directory
                        if os.path.exists(output_base_dir) and os.path.isdir(output_base_dir):
                            project_dirs = [d for d in os.listdir(output_base_dir) 
                                           if os.path.isdir(os.path.join(output_base_dir, d))]

                            if project_name and project_name in project_dirs:
                                # Found the project directory
                                actual_output_dir = os.path.join(output_base_dir, project_name)
                                st.success(f"Found output directory at: {actual_output_dir}")

                                # List files for download and viewing
                                st.markdown("### Tutorial Content")
                                files = sorted(os.listdir(actual_output_dir))
                                if files:
                                    # Create tabs for each file plus a "Complete Tutorial" tab
                                    tab_names = [f.replace('.md', '') for f in files]
                                    tab_names.append("Complete Tutorial")
                                    tabs = st.tabs(tab_names)

                                    # Prepare combined content for the complete tutorial
                                    combined_content = ""
                                    file_contents = {}

                                    # First, read all file contents
                                    for file in files:
                                        file_path = os.path.join(actual_output_dir, file)
                                        if os.path.isfile(file_path) and file.endswith('.md'):
                                            try:
                                                with open(file_path, "r", encoding="utf-8") as f:
                                                    file_contents[file] = f.read()
                                            except Exception as e:
                                                file_contents[file] = f"Error reading file: {str(e)}"

                                    # Process individual tabs
                                    for i, file in enumerate(files):
                                        if file in file_contents:
                                            content = file_contents[file]

                                            # Display the content in the corresponding tab
                                            with tabs[i]:
                                                # Add download button at the top
                                                with open(os.path.join(actual_output_dir, file), "rb") as f:
                                                    st.download_button(
                                                        label=f"Download {file}",
                                                        data=f,
                                                        file_name=file,
                                                        mime="text/markdown"
                                                    )

                                                # Display the markdown content
                                                st.markdown(content)

                                    # Create combined content using our utility function
                                    combined_content, combined_file_path = create_combined_markdown(
                                        file_contents, 
                                        os.path.join(actual_output_dir, "complete_tutorial.md")
                                    )

                                    # Display the complete tutorial tab
                                    with tabs[-1]:
                                        if combined_content and combined_file_path:
                                            # Add download buttons for markdown
                                            with open(combined_file_path, "rb") as f:
                                                st.download_button(
                                                    label="Download Complete Tutorial (Markdown)",
                                                    data=f,
                                                    file_name="complete_tutorial.md",
                                                    mime="text/markdown"
                                                )

                                            # Convert to HTML for better rendering
                                            html_content = markdown_to_html(combined_content)
                                            if html_content:
                                                # Save HTML file
                                                html_file_path = os.path.join(actual_output_dir, "complete_tutorial.html")
                                                with open(html_file_path, "w", encoding="utf-8") as f:
                                                    f.write(html_content)

                                                # Add download button for HTML
                                                with open(html_file_path, "rb") as f:
                                                    st.download_button(
                                                        label="Download Complete Tutorial (HTML)",
                                                        data=f,
                                                        file_name="complete_tutorial.html",
                                                        mime="text/html"
                                                    )

                                            # Convert to PDF and add PDF download button
                                            try:
                                                with st.spinner("Converting to PDF..."):
                                                    # Create a file for the PDF
                                                    pdf_file_path = os.path.join(actual_output_dir, "complete_tutorial.pdf")

                                                    # Convert markdown to PDF
                                                    pdf_path = markdown_to_pdf(combined_content, pdf_file_path)

                                                    if pdf_path and os.path.exists(pdf_path):
                                                        with open(pdf_path, "rb") as f:
                                                            st.download_button(
                                                                label="Download Complete Tutorial (PDF)",
                                                                data=f,
                                                                file_name="complete_tutorial.pdf",
                                                                mime="application/pdf"
                                                            )
                                                    else:
                                                        st.warning("PDF conversion failed. Please download the HTML or markdown version instead.")
                                            except Exception as e:
                                                st.warning(f"PDF conversion failed: {str(e)}. Please download the HTML or markdown version instead.")

                                            # Display the combined content with proper rendering
                                            st.markdown("## Complete Tutorial")
                                            st.markdown("This tab shows all chapters combined into a single document.")

                                            # Use HTML display for better rendering of Mermaid diagrams
                                            if html_content:
                                                st.components.v1.html(html_content, height=800, scrolling=True)
                                            else:
                                                # Fallback to regular markdown display
                                                st.markdown(combined_content)
                                        else:
                                            st.error("Failed to create combined tutorial content.")
                                else:
                                    st.info("No files found in the output directory.")
                            else:
                                # List all available project directories
                                if project_dirs:
                                    st.warning(f"Output directory '{output_dir}' not found, but found these project directories:")
                                    for dir_name in project_dirs:
                                        dir_path = os.path.join(output_base_dir, dir_name)
                                        st.info(f"- {dir_path}")
                                else:
                                    st.warning(f"Output directory '{output_dir}' not found and no project directories found in {output_base_dir}")
                        else:
                            st.warning(f"Output directory not found or not accessible: {output_dir}")
                else:
                    # Try to find any output directories
                    output_base_dir = shared.get("output_dir", "output")
                    if os.path.exists(output_base_dir) and os.path.isdir(output_base_dir):
                        project_dirs = [d for d in os.listdir(output_base_dir) 
                                       if os.path.isdir(os.path.join(output_base_dir, d))]
                        if project_dirs:
                            st.success("Tutorial generation completed! Found these output directories:")
                            for dir_name in project_dirs:
                                dir_path = os.path.join(output_base_dir, dir_name)
                                st.info(f"- {dir_path}")
                        else:
                            st.warning(f"Tutorial generation completed but no output directories found in {output_base_dir}")
                    else:
                        st.warning("Tutorial generation completed but output directory not found.")
            except Exception as e:
                progress_bar.progress(100)
                status_text.text("Tutorial generation failed!")
                st.error(f"Error generating tutorial: {str(e)}")
                st.exception(e)

        except Exception as e:
            st.error(f"Error generating tutorial: {str(e)}")
            st.exception(e)

# Display information about the app
st.markdown("---")
st.markdown("""
### How it works
1. The app clones the GitHub repository, reading local path or uploaded files
2. It analyzes the codebase structure and identifies key abstractions
3. It determines relationships between components
4. It generates tutorial chapters in a logical order
5. Finally, it combines everything into a comprehensive tutorial
### Requirements
- A public GitHub repository
- Google Gemini API access (configured via environment variables)
""")
