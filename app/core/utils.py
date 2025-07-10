import os
from datetime import datetime

def create_markdown_note(title: str, summary: str, output_dir: str = "app/output") -> str:
    """
    Creates a Markdown note with the given title and summary.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{title.replace(' ', '_').lower()}.md"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w") as f:
        f.write(f"# {title}\n\n")
        f.write("## Summary\n\n")
        f.write(f"{summary}\n")

    return filepath
