from dataclasses import dataclass
from typing import Optional


@dataclass
class SignBoxPlaceholder:
    """
    Represents a placeholder for a SignBox with positional and size attributes.
    """
 
    x: int
    y: int
    width: int
    height: int
    pag: Optional[int] = None  # Campo opzionale per il numero di pagina
 
    def __repr__(self):
        """
        Returns a string representation of the SignBoxPlaceholder instance.
 
        Returns:
            str: A readable string representation of the instance.
        """
        return f"SignBoxPlaceholder(x={self.x}, y={self.y}, width={self.width}, height={self.height}, pag={self.pag})"
 
    def change_reference_point(self, page_width: int, page_height: int) -> tuple:
        """
        Changes the reference point of the coordinates from the top-left corner
        to the bottom-left corner of a page.
 
        Args:
            page_width (int): The width of the page.
            page_height (int): The height of the page.
 
        Returns:
            tuple: The new coordinates (x, y) with the bottom-left corner as the reference point.
        """
        new_x = self.x
        new_y = page_height - self.y
        return new_x, new_y
