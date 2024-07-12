import sys
from PIL import Image
import png
import io

def process_image(filename, out_base):
    normal, shiny = split_normal_and_shiny(filename)

    normal_rgb = image_to_RGB_array(normal)
    shiny_rgb = image_to_RGB_array(shiny)
    
    normal_palette = get_palette(normal_rgb)
    shiny_palette = get_palette(shiny_rgb)

    issues = detect_palette_issues(normal_palette, shiny_palette)
    diff_filename = None
    # Align the shiny and normal palettes to use the same indexes for the same pixels
    # Make shiny sprite primary if it has fewer colors than normal
    shiny_is_primary = len(shiny_palette) < len(normal_palette)
    if shiny_is_primary:
        shiny_palette = move_background_first(shiny_palette, shiny_rgb, width=128)
        mapping, problem_colors, mapping_issues = get_palette_mapping(shiny_palette, shiny_rgb, normal_palette, normal_rgb, primary_label='Shiny', secondary_label='Normal')
        issues.extend(mapping_issues)
        if (len(problem_colors) > 0):
            highlighted = highlight_problem_colors(normal_rgb, problem_colors, shiny_rgb, mapping, shiny_palette, normal_palette)
            diff_filename = save_diff(highlighted, out_base)
        else:
            normal_palette = map_palette(normal_palette, mapping)
    else:
        normal_palette = move_background_first(normal_palette, normal_rgb, width=128)
        mapping, problem_colors, mapping_issues = get_palette_mapping(normal_palette, normal_rgb, shiny_palette, shiny_rgb)
        issues.extend(mapping_issues)
        if (len(problem_colors) > 0):
            highlighted = highlight_problem_colors(shiny_rgb, problem_colors, normal_rgb, mapping, normal_palette, shiny_palette)
            diff_filename = save_diff(highlighted, out_base)
        else:
            shiny_palette = map_palette(shiny_palette, mapping)

    if len(issues) > 0:
        # raise Exception('Unable to index sprites:\n' + '\n'.join(issues))
        return {
            "success": False,
            "issues": issues,
            "diff_filename": diff_filename
        }
    
    
    front = normal.crop((0, 0, 64, 64))
    back = normal.crop((64, 0, 128, 64))
    front_file_name = out_base + 'front.png'
    back_file_name = out_base + 'back.png'
    palette_file_name = out_base + 'normal.pal'
    shiny_palette_file_name = out_base + 'shiny.pal'
    save_image(image_to_RGB_array(front), normal_palette, front_file_name)
    save_image(image_to_RGB_array(back), normal_palette, back_file_name)
    save_palette(normal_palette, palette_file_name)
    save_palette(shiny_palette, shiny_palette_file_name)
    # return front_file_name, back_file_name, palette_file_name, shiny_palette_file_name
    return {
        "success": True,
        "front_file_name": front_file_name,
        "back_file_name": back_file_name,
        "palette_file_name": palette_file_name,
        "shiny_palette_file_name": shiny_palette_file_name
    }

def split_normal_and_shiny(filename):
    with Image.open(filename) as img:
        front = img.crop((0, 0, 64, 64))
        front_shiny = img.crop((64, 0, 128, 64))
        back = img.crop((128, 0, 192, 64))
        back_shiny = img.crop((192, 0, 256, 64))

        # Create temp images combining the front and back to ensure the
        # palette includes all colors used in both in a consistent order
        normal = Image.new(mode='RGB', size=(128, 64))
        normal.paste(front, (0,0))
        normal.paste(back, (64, 0))

        shiny = Image.new(mode='RGB', size=(128, 64))
        shiny.paste(front_shiny, (0,0))
        shiny.paste(back_shiny, (64, 0))

        return (normal, shiny)

# Convert image to array of RGB tuples [(r,g,b), (r,g,b), ...]
def image_to_RGB_array(img: Image):
    return list(img.getdata())

def rgb_tuple_to_hex(rgb):
    return '#%02x%02x%02x' % rgb

# Extract unique colors from array of RGB tuples [(r,g,b), (r,g,b), ...]
def get_palette(rgbArray):
    palette = []
    for rgb in rgbArray:
        if rgb not in palette:
            palette.append(rgb)
    return palette

def detect_palette_issues(normal_palette, shiny_palette):
    issues = []
    # Confirm that normal and shiny palettes are the same length
    if len(normal_palette) != len(shiny_palette):
        issues.append('Normal palette has %d colors, but shiny palette has %d colors' % (len(normal_palette), len(shiny_palette)))
    # Confirm that normal and shiny palettes are both at most 16 colors
    elif len(normal_palette) > 16:
        issues.append('Normal palette has more than 16 colors (%d colors()' % len(normal_palette))
    elif len(shiny_palette) > 16:
        issues.append('Shiny palette has more than 16 colors (%d colors()' % len(shiny_palette))
    return issues

# Assume that background color is the color at the most corners of the image
def move_background_first(palette, rgb_array, width=64):
    # Get the color at each of the four corners of the image
    top_left = rgb_array[0]
    top_right = rgb_array[width-1]
    bottom_left = rgb_array[-width]
    bottom_right = rgb_array[-1]
    corners =  [top_left, top_right, bottom_left, bottom_right]
    # Find the color that occurs the most times in the corners array
    most_common = max(set(corners), key=corners.count)
    # Find the index of the most common color in the palette
    bg_color_index = palette.index(most_common)
    # Move the background color to the first index in the palette
    palette.insert(0, palette.pop(bg_color_index))
    return palette

# Produce a best attempt at a mapping of indexes from one palette to another
# by comparing pixel colors between primary image and secondary image and assuming
# that the color that matches most often is the best match
def get_palette_mapping(primary_palette, primary_img, secondary_palette, secondary_img, primary_label='Normal', secondary_label='Shiny'):
    mapping = {}
    problem_colors = set()
    issues = []

    potential_mappings = {}
    for i in range(len(primary_palette)):
        primary_color = primary_palette[i]
        secondary_color_counts = {}
        for j in range(len(primary_img)):
            if primary_img[j] == primary_color:
                secondary_color = secondary_img[j]
                secondary_color_counts[secondary_color] = secondary_color_counts.get(secondary_color, 0) + 1
        potential_mappings[i] = secondary_color_counts
    # Put the most common secondary color in the mapping for each primary color.
    # For any color that maps to more than one color in the secondary palette,
    # log a message about the non-matching colors
    for i in range(len(primary_palette)):
        primary_color = primary_palette[i]
        secondary_color_counts = potential_mappings[i]
        secondary_color = max(secondary_color_counts, key=secondary_color_counts.get)
        if len(secondary_color_counts) > 1:
            # Format color counts as a list of hex values with pixel counts (ex. "#ff0000 (2 pixels), #00ff00 (1 pixel)") in order of count descending
            ordered_color_counts = sorted(secondary_color_counts.items(), key=lambda x: x[1], reverse=True)
            formatted_counts =  [rgb_tuple_to_hex(color) + ' (' + str(count) + ' pixels)' for color, count in ordered_color_counts]
            issues.append('%s color %s maps to multiple %s colors: %s' % (primary_label, rgb_tuple_to_hex(primary_color), secondary_label, ', '.join(formatted_counts)))
            # Add non-matching colors to the problem colors set
            problem_colors.update(set(secondary_color_counts.keys()) - {secondary_color})
        mapping[i] = secondary_palette.index(secondary_color)

    return (mapping, problem_colors, issues)

def map_palette(palette, mapping):
    mapped_palette = []
    for i in range(len(palette)):
        mapped_palette.append(palette[mapping[i]])
    return mapped_palette

# Highlight the problem colors in the image by replacing them with pure magenta
def highlight_problem_colors(rgb_array, problem_colors, primary_img, mapping, primary_palette, secondary_palette):
    secondary_to_primary_color_mapping = {secondary_palette[mapping[i]]: primary_palette[i] for i in range(len(mapping))}
    for i in range(len(rgb_array)):
        if rgb_array[i] in problem_colors:
            primary_color = secondary_to_primary_color_mapping.get(rgb_array[i], None)
            if primary_color == None or primary_img[i] != primary_color:
                rgb_array[i] = (255, 0, 255)
    return rgb_array

def save_image(rgb_array, palette, filename, width=64, bit_depth=4):
    with open(filename, 'wb') as f:
        # Convert RGB array to PyPng list of palette indexes
        color_to_index = {color: index for index, color in enumerate(palette)}
        palette_indexes = [color_to_index[color] for color in rgb_array]
        # Create a new PyPng image with the palette
        w = png.Writer(width=width, height=int(len(rgb_array)/width), palette=palette, bitdepth=bit_depth)
        w.write_array(f, palette_indexes)

def save_palette(palette, filename):
    with io.open(filename, 'w', newline='\r\n') as f:
        f.write('JASC-PAL\n0100\n16\n')
        # If palette has less than 16 colors, pad it with black
        if len(palette) < 16:
            palette.extend([(0, 0, 0)] * (16 - len(palette)))
            
        for color in palette[:16]:
            f.write(f'{color[0]} {color[1]} {color[2]}\n')

def save_diff(rgb_array, out_base):
    palette = get_palette(rgb_array)
    filename = out_base + 'diff.png'
    save_image(rgb_array, palette, filename, bit_depth=8, width=128)
    # Make 4x scaled copy
    scaled_filename = filename.replace('.png', '_4x.png')
    with Image.open(filename) as img:
        img.resize((img.width * 4, img.height * 4)).save(scaled_filename)
    return scaled_filename
