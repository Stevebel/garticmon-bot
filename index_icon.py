import sys
from PIL import Image
from os import path
import math

def process_image(filename, outname, targetPal):
    with Image.open(filename) as img:
        with Image.open(targetPal) as palImg:
            c = img.convert(mode='RGB').quantize(colors=16, dither=Image.NONE)
            bottomRight = c.getpixel((c.width - 1, c.height - 1))
            if (bottomRight != 0):
                swapPalette(c, bottomRight, 0)
            changePaletteZero(c, palImg.getpalette()[0:3])
            matchPalette(c, palImg)
            c.info['transparency'] = None
            clearPaletteAfter16(c)
            c.save(outname)
            print('Saved output to ', outname)
            return outname

def swapPalette(img, fromIdx, toIdx):
    pal = img.getpalette()
    valToMove = pal[toIdx * 3: (toIdx + 1) * 3]
    for i in range(3):
        pal[(toIdx * 3) + i] = pal[(fromIdx * 3) + i]
        pal[(fromIdx * 3) + i] = valToMove[i]
    img.putpalette(pal)
    swapColor(img, fromIdx, toIdx)

def swapColor(img, fromVal, toVal):
    data = list(img.getdata())
    for i in range(len(data)):
        if (data[i] == fromVal):
            data[i] = toVal
        elif(data[i] == toVal):
            data[i] = fromVal
    img.putdata(data)

def changePaletteZero(img, color = [255, 0, 255]):
    pal = img.getpalette()
    pal[0:3] = color
    img.putpalette(pal)

def clearPaletteAfter16(img):
    pal = img.getpalette()
    for i in range(48, len(pal)):
        pal[i] = 0
    img.putpalette(pal)

def matchPalette(img, palImg):
    targetPal = paletteToTuples(palImg.getpalette()[0:48])
    currPal = paletteToTuples(img.getpalette()[0:len(img.getcolors()) * 3])
    targetIdx = [closestIndex(currPal[i], targetPal) for i in range(len(currPal))]
    data = list(img.getdata())
    for i in range(len(data)):
        if (data[i] < len(targetIdx)):
            data[i] = targetIdx[data[i]]
        else:
            data[i] = 0
    img.putdata(data)
    img.putpalette(palImg.getpalette())

def paletteToTuples(pal):
    return list(zip(*[pal[i::3] for i in range(3)]))

def closestIndex(c, pal):
    # If the color is in the palette, return its index
    if (c in pal):
        return pal.index(c)
    # Otherwise, find the closest color in the palette
    min_d = float('inf')
    best = 0
    r1, g1, b1 = c
    for i, (r2, g2, b2) in enumerate(pal[1:]):
        # Color diff from https://stackoverflow.com/questions/1847092/given-an-rgb-value-what-would-be-the-best-way-to-find-the-closest-match-in-the-d
        d = ((r2-r1)*0.30)**2 + ((g2-g1)*0.59)**2 + ((b2-b1)*0.11)**2
        if d < min_d:
            min_d = d
            best = i
    return best + 1

def getDistance(c1, c2):
    # Get simple Euclidean distance in RGB space.
    # This is a very poor approximation but works fine as long as
    # the colors are very close to the palette
    r = abs(c2[0] - c1[0])
    g = abs(c2[1] - c1[1])
    b = abs(c2[2] - c2[2])
    return math.sqrt(r*r + g*g + b*b)

if __name__ == '__main__':
    palNum = sys.argv[1]
    filename = sys.argv[2]
    outname = filename.replace('.png', '') + '_fixed.png'
    if (len(sys.argv) > 3):
        outname = sys.argv[3]
    print('Indexing ' + filename + ' to palette #' + palNum)
    process_image(filename, outname, path.join('assets', 'palettes', 'IconPalette' + palNum + '.png'))
