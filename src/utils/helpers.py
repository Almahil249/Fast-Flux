import re

def generate_url(base_url: str, index: int, padding: str = None) -> str:
    """
    Generates a URL by replacing [index] or [i] with the formatted index.
    padding: "00" -> width 2, "000" -> width 3. None -> no padding (just str(index)).

    Test Case:
    >>> generate_url("http://test.com/img_[i].jpg", 5, "00")
    'http://test.com/img_05.jpg'
    >>> generate_url("http://site.com/v[INDEX].ts", 1)
    'http://site.com/v1.ts'
    """
    # Strip whitespace/newlines
    base_url = base_url.strip()

    idx_str = str(index)
    if padding:
        width = len(padding)
        idx_str = f"{index:0{width}d}"
    
    # Case-insensitive replacement for [index] or [i]
    return re.sub(r'\[(?:index|i)\]', idx_str, base_url, flags=re.IGNORECASE)

def get_example_urls(base_url: str, start: int, end: int, padding: str = None) -> tuple[str, str]:
    """Returns the first and last URL for validation."""
    first = generate_url(base_url, start, padding)
    last = generate_url(base_url, end, padding)
    return first, last
