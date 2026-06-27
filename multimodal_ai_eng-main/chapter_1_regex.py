import re

def is_bill_filename(filename: str) -> bool:
    pattern = r"^bill_[a-zA-Z]+_\d+\.(png|jpg|jpeg)$"
    return bool(re.match(pattern, filename))


# Usage
if __name__ == "__main__":
    filename = "bill_innovh_01.png"
    print(f"Is bill filename: {is_bill_filename(filename)}")