# flake8: noqa: WPS100


def row_label(row_number: int) -> str:
    label = ""
    remaining_value = row_number
    while remaining_value > 0:
        remaining_value, remainder = divmod(remaining_value - 1, 26)
        label = chr(ord("A") + remainder) + label
    return label or "A"
