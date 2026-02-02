def generate_url(base_url: str, index: int, padding: str = None) -> str:
    """
    Generates a URL by replacing [index] with the formatted index.
    padding: "00" -> width 2, "000" -> width 3. None -> no padding (just str(index)).
    """
    if "[index]" not in base_url:
        return base_url

    idx_str = str(index)
    if padding:
        width = len(padding)
        idx_str = f"{index:0{width}d}"
    
    return base_url.replace("[index]", idx_str)

def get_example_urls(base_url: str, start: int, end: int, padding: str = None) -> tuple[str, str]:
    """Returns the first and last URL for validation."""
    first = generate_url(base_url, start, padding)
    last = generate_url(base_url, end, padding)
    return first, last
