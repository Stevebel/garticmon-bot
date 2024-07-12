from PIL import Image

from index_spritesheet import get_palette, rgb_tuple_to_hex


def test_icon(filename, targetPal):
    with Image.open(filename) as img:
        with Image.open(targetPal) as palImg:
            icon_palette = get_palette(img)
            target_palette = get_palette(palImg)
            issues = detect_palette_issues(icon_palette, target_palette)
            return issues


# Detect colors in icon palette that don't exist in target palette
def detect_palette_issues(icon_palette, target_palette, icon_img: Image):
    issues = []
    if len(icon_palette) > 16:
        issues.append(
            "Icon palette has more than 16 colors (%d colors()" % len(icon_palette)
        )
        return issues
    icon_palette_set = set(icon_palette)
    target_palette_set = set(target_palette)
    extra_colors = icon_palette_set - target_palette_set
    if len(extra_colors) > 0:
        color_counts = {}
        for i in range(len(icon_img)):
            color = icon_img[i]
            if color in extra_colors:
                color_counts[color] = color_counts.get(color, 0) + 1
        # Format color counts as a list of hex values with pixel counts (ex. "#ff0000 (2 pixels), #00ff00 (1 pixel)") in order of count descending
        ordered_color_counts = sorted(
            color_counts.items(), key=lambda x: x[1], reverse=True
        )
        formatted_counts = [
            rgb_tuple_to_hex(color) + " (" + str(count) + " pixels)"
            for color, count in ordered_color_counts
        ]
        issues.append(
            "Extra colors in icon palette compared to the battle sprite: %s"
            % ", ".join(formatted_counts)
        )
    return issues
