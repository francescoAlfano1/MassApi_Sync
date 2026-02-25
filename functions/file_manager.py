import os
import logging
import time
import pypdf
from classes.Data import SignBoxPlaceholder
from typing import Dict, List, Tuple, Union


def move_file(source_path: str, destination_path: str, filename: str) -> None:
    """
    Move a file from source_path to destination_path.
    """
    try:
        # Try create destination Folder
        os.makedirs(destination_path, exist_ok=True)
        destination = os.path.join(
            destination_path, f"{filename}_{time.time()}.pdf"
        ).replace("\\", "/")
        os.rename(source_path, destination)
        logging.info(f"Moved file from {source_path} to {destination}")
    except Exception as e:
        logging.error(
            f"Error moving file from {source_path} to {destination_path}: {e}"
        )

def get_page_count(file_path: str) -> int:
    """
    Get the number of pages in a PDF file.

    Args:
        file_path (str): Path to the PDF file.

    Returns:
        int: Number of pages in the PDF file.
    """
    try:
        with open(file_path, "rb") as file:
            reader = pypdf.PdfReader(file)
            return len(reader.pages)
    except Exception as e:
        logging.error(f"Error reading PDF file {file_path}: {e}")
        raise e


# These functions were originally created to search for specific anchors in the PDF file using the format `@@text@@`.
# Although we decided not to use them anymore, they are left here in case we decide to reintroduce anchor-based navigation in the future.
def anchor_text_check(text: str) -> bool:
    return text.startswith("@@") and text.endswith("@@")


def search_anchor_in_pdf(
    file_path: str, anchorbox_dict: Dict[str, SignBoxPlaceholder]
) -> Dict[str, str]:
    """
    Search for an anchor in a PDF file.
    """
    user_dict = {}
    page_width = (0,)
    page_height = 0

    def extract_text_agent(
        text: str, _current_matrix, transformation_matrix, _font_dict, _font_size
    ):
        """
        Callback function used to process text extracted from a PDF page.

        Args:
            text (str): The extracted text from the PDF page.
            _current_matrix: Current transformation matrix (not used in this function).
            transformation_matrix: Transformation matrix containing the text's coordinates.
            _font_dict: Font dictionary (not used in this function).
            _font_size: Font size (not used in this function).
        """
        if not anchor_text_check(text):
            return

        # Extract the (x, y) coordinates from the transformation matrix
        (x, y) = transformation_matrix[4], transformation_matrix[5]

        # Iterate through the SignBoxPlaceholder objects in the signbox_dict
        for key, box in anchorbox_dict.items():
            # Adjust the box's reference point based on the page dimensions
            box_x, box_y = box.change_reference_point(page_width, page_height)

            # Check if the (x, y) coordinates fall within the box's boundaries
            if box_x < x < (box_x + box.width) and (box_y - box.height) < y < box_y:
                user_dict[key] = text.replace("@@", "")

    try:
        with open(file_path, "rb") as file:
            reader = pypdf.PdfReader(file)
            last_page = reader.pages[-1]
            page_width = round(last_page.mediabox.width)
            page_height = round(last_page.mediabox.height)
            last_page.extract_text(visitor_text=extract_text_agent)
            return user_dict
    except Exception as e:
        logging.error(f"Error reading PDF file {file_path}: {e}")
        raise e
