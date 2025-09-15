def clean_text(text):
    """
    Cleans input text by stripping whitespace and converting to lowercase.
    """
    return text.strip().lower()

if __name__ == "__main__":
    sample = "  Hello, GitHub!  "
    print("Before:", sample)
    print("After:", clean_text(sample))
