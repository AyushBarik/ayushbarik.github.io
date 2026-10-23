"""Build the Minecraft-block photomosaic used for the sidebar profile picture.

Every cell of a square grid over the photo is replaced by the Minecraft block texture whose
colors best match that patch. The browser (js/block-mosaic.js) draws the mosaic from a small
atlas of the blocks that were used plus a grid of indices into it, so the page loads ~100 KB
instead of a multi-megabyte pre-rendered image, and zooming stays pixel-sharp.

Block textures are not committed; pull them (and the block models, which say which textures
cover a whole cube) out of the official client jar first:

    curl -s https://piston-meta.mojang.com/mc/game/version_manifest_v2.json   # -> version json -> client.jar
    unzip client.jar 'assets/minecraft/textures/block/*' 'assets/minecraft/models/block/*' \
        'assets/minecraft/blockstates/*' -d mc

The current picture was built with:

    python scripts/build_mosaic.py --textures mc/assets/minecraft/textures/block \
        --photo assets/metoo.jpg --crop 0 650 2750 3350

Needs Pillow and numpy.
"""

import argparse
import base64
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

TILE = 16          # Minecraft block textures are 16x16
SUB = 4            # each cell is matched as a SUB x SUB grid of colors, so texture detail lines up with edges
ATLAS_COLS = 16

# Textures that are drawn grayscale in the jar and tinted in game (by biome, or redstone power).
# Tint them with the plains colors so they look like they do in the world.
GRASS, FOLIAGE, STEM = (0x91, 0xBD, 0x59), (0x77, 0xAB, 0x2F), (0xE0, 0xC7, 0x1C)
TINTS = {
    'grass_block_top': GRASS, 'grass_block_side_overlay': GRASS, 'short_grass': GRASS,
    'tall_grass_top': GRASS, 'tall_grass_bottom': GRASS, 'fern': GRASS, 'large_fern_top': GRASS,
    'large_fern_bottom': GRASS, 'sugar_cane': GRASS, 'bush': GRASS,
    'oak_leaves': FOLIAGE, 'jungle_leaves': FOLIAGE, 'acacia_leaves': FOLIAGE, 'dark_oak_leaves': FOLIAGE,
    'vine': FOLIAGE, 'birch_leaves': (0x80, 0xA7, 0x55), 'spruce_leaves': (0x61, 0x99, 0x61),
    'mangrove_leaves': (0x8D, 0xB1, 0x27), 'lily_pad': (0x20, 0x80, 0x30),
    'water_still': (0x3F, 0x76, 0xE4), 'water_flow': (0x3F, 0x76, 0xE4), 'water_overlay': (0x3F, 0x76, 0xE4),
    'redstone_dust_dot': (0xFC, 0x32, 0x00), 'redstone_dust_line0': (0xFC, 0x32, 0x00),
    'redstone_dust_line1': (0xFC, 0x32, 0x00),
    'melon_stem': STEM, 'pumpkin_stem': STEM, 'attached_melon_stem': STEM, 'attached_pumpkin_stem': STEM,
}

# With --no-filter, see-through pixels are drawn over the gray of an inventory slot.
BACKDROP = (0x8B, 0x8B, 0x8B)



def srgb_to_lab(rgb):
    """rgb: float array in [0, 1], shape (..., 3). Returns CIE Lab (D65)."""
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16,
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], axis=-1)


def linear(rgb):
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def delinear(lin):
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.clip(lin, 0, None) ** (1 / 2.4) - 0.055)


def full_cube_textures(assets_dir):
    """Names of the textures drawn on a face of a whole 16x16x16 cube in some block's model, so
    stone and logs count but anvils, doors, beds and slabs-only textures don't."""
    models = {}

    def model(ref):
        name = ref.split(':')[-1]
        if name not in models:
            path = assets_dir / 'models' / f'{name}.json'
            data = json.loads(path.read_text()) if path.exists() else {}
            textures, elements = {}, None
            if 'parent' in data:
                textures, elements = model(data['parent'])
                textures = dict(textures)
            textures.update(data.get('textures', {}))
            models[name] = (textures, data.get('elements', elements))
        return models[name]

    def resolve(ref, textures):
        for _ in range(10):
            if isinstance(ref, dict):
                ref = ref.get('sprite', '')
            if not ref.startswith('#'):
                return ref.split(':')[-1]
            ref = textures.get(ref[1:], '')
        return ''

    found = set()
    for path in (assets_dir / 'blockstates').glob('*.json'):
        state = json.loads(path.read_text())
        refs = list(state.get('variants', {}).values()) + [part['apply'] for part in state.get('multipart', [])]
        for ref in refs:
            for variant in ref if isinstance(ref, list) else [ref]:
                textures, elements = model(variant['model'])
                for element in elements or []:
                    if element['from'] == [0, 0, 0] and element['to'] == [16, 16, 16]:
                        for face in element['faces'].values():
                            texture = resolve(face['texture'], textures)
                            if texture.startswith('block/'):
                                found.add(texture[len('block/'):])
    return found


def load_blocks(tex_dir, keep_all=False):
    """Returns (names, textures uint8 [n,16,16,3]) for every solid face of a full-cube block, or with
    keep_all for every texture in the directory (see-through ones flattened onto BACKDROP)."""
    full_cube = None if keep_all else full_cube_textures(Path(tex_dir).parent.parent)
    names, textures, seen = [], [], set()
    for path in sorted(Path(tex_dir).glob('*.png')):
        name = path.stem
        if full_cube is not None and name not in full_cube:
            continue
        img = Image.open(path).convert('RGBA')
        w, h = img.size
        if not keep_all and (w != TILE or h % TILE):
            continue
        # Animated textures are vertical strips of square frames; keep the first frame. Signs and
        # shelves are 32px model layouts, which get shrunk down to one 16px tile.
        img = img.crop((0, 0, w, w))
        if w != TILE:
            img = img.resize((TILE, TILE), Image.BOX)
        px = np.asarray(img).astype(np.float32)
        if not keep_all and px[..., 3].min() < 255:     # full cubes you can see through (glass, leaves)
            continue
        rgb = px[..., :3]
        if name in TINTS:
            rgb = rgb * np.array(TINTS[name]) / 255
        alpha = px[..., 3:] / 255
        rgb = (rgb * alpha + np.array(BACKDROP) * (1 - alpha)).round().astype(np.uint8)
        key = rgb.tobytes()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
        textures.append(rgb)
    return names, np.stack(textures)


def downsample(rgb_u8, size):
    """Box-filter [..., H, W, 3] uint8 sRGB down to [..., size, size, 3] sRGB floats, averaging in linear light."""
    lin = linear(rgb_u8.astype(np.float64) / 255)
    *lead, h, w, c = lin.shape
    lin = lin.reshape(*lead, size, h // size, size, w // size, c).mean(axis=(-4, -2))
    return delinear(lin)


def build(photo_path, crop, tex_dir, cols, structure_weight, dither, keep_all):
    names, textures = load_blocks(tex_dir, keep_all)
    print(f'{len(names)} candidate blocks')

    block_sub = srgb_to_lab(downsample(textures, SUB)).reshape(len(names), SUB * SUB, 3)
    block_mean = srgb_to_lab(downsample(textures, 1)).reshape(len(names), 3)
    block_dev = block_sub - block_mean[:, None]

    photo = ImageOps.exif_transpose(Image.open(photo_path)).convert('RGB')
    if crop:
        left, top, width, height = crop
        photo = photo.crop((left, top, left + width, top + height))
    rows = round(cols * photo.height / photo.width)
    photo = photo.resize((cols * SUB, rows * SUB), Image.LANCZOS)
    target = srgb_to_lab(np.asarray(photo, dtype=np.float64) / 255)
    target = target.reshape(rows, SUB, cols, SUB, 3).transpose(0, 2, 1, 3, 4).reshape(rows, cols, SUB * SUB, 3)

    # Floyd-Steinberg error diffusion on each cell's mean color (serpentine), so large flat areas
    # mix neighboring blocks to hit in-between shades the block palette doesn't have.
    error = np.zeros((rows + 1, cols + 2, 3))
    grid = np.zeros((rows, cols), dtype=np.int32)
    for y in range(rows):
        xs = range(cols) if y % 2 == 0 else range(cols - 1, -1, -1)
        step = 1 if y % 2 == 0 else -1
        for x in xs:
            want = target[y, x] + error[y, x + 1]
            want_mean = want.mean(axis=0)
            cost = ((block_mean - want_mean) ** 2).sum(axis=1)
            cost += structure_weight * ((block_dev - (want - want_mean)) ** 2).sum(axis=(1, 2)) / (SUB * SUB)
            best = int(cost.argmin())
            grid[y, x] = best
            err = (want_mean - block_mean[best]) * dither
            error[y, x + 1 + step] += err * 7 / 16
            error[y + 1, x + 1 - step] += err * 3 / 16
            error[y + 1, x + 1] += err * 5 / 16
            error[y + 1, x + 1 + step] += err * 1 / 16
    return names, textures, grid


def main():
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--textures', required=True, help='directory of block PNGs from the client jar')
    ap.add_argument('--photo', default=root / 'assets/metoo.jpg')
    ap.add_argument('--crop', type=int, nargs=4, metavar=('LEFT', 'TOP', 'WIDTH', 'HEIGHT'),
                    help='part of the photo to use, in pixels (default: all of it)')
    ap.add_argument('--out', default=root / 'assets/mosaic')
    ap.add_argument('--cols', type=int, default=125, help='blocks across; the number of rows follows the photo\'s shape')
    ap.add_argument('--structure-weight', type=float, default=1.0,
                    help='how much the pattern inside a block should follow the photo, vs. only its average color')
    ap.add_argument('--dither', type=float, default=0.6, help='fraction of color error passed to neighbors')
    ap.add_argument('--no-filter', action='store_true',
                    help='use every block texture, not just the solid faces of full-cube blocks')
    ap.add_argument('--preview', help='also write the full-resolution mosaic here')
    args = ap.parse_args()

    names, textures, grid = build(args.photo, args.crop, args.textures, args.cols, args.structure_weight, args.dither, args.no_filter)

    used = np.unique(grid)
    remap = np.zeros(len(names), dtype=np.int32)
    remap[used] = np.arange(len(used))
    cells = remap[grid]
    rows, cols = grid.shape
    print(f'{cols}x{rows} grid, {len(used)} distinct blocks used')

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    atlas_rows = -(-len(used) // ATLAS_COLS)
    atlas = np.zeros((atlas_rows * TILE, ATLAS_COLS * TILE, 3), dtype=np.uint8)
    for i, b in enumerate(used):
        r, c = divmod(i, ATLAS_COLS)
        atlas[r * TILE:(r + 1) * TILE, c * TILE:(c + 1) * TILE] = textures[b]
    Image.fromarray(atlas).save(out / 'blocks.png', optimize=True)

    dtype = np.uint8 if len(used) <= 256 else np.uint16
    data = {
        'cols': cols,
        'rows': rows,
        'tile': TILE,
        'atlasCols': ATLAS_COLS,
        'bytesPerCell': np.dtype(dtype).itemsize,
        'names': [names[b] for b in used],
        'cells': base64.b64encode(cells.astype(dtype).astype(f'<{np.dtype(dtype).str[1:]}').tobytes()).decode(),
    }
    # A script rather than JSON so it also loads when index.html is opened straight from disk.
    (out / 'mosaic-data.js').write_text(
        '// Generated by scripts/build_mosaic.py; do not edit.\nwindow.BLOCK_MOSAIC = ' + json.dumps(data) + ';\n')

    full = textures[grid].transpose(0, 2, 1, 3, 4).reshape(rows * TILE, cols * TILE, 3)
    full_img = Image.fromarray(full)
    # Static version for first paint and no-JS: 400px covers the 200px sidebar on 2x screens.
    full_img.resize((400, round(400 * rows / cols)), Image.LANCZOS).save(out / 'mosaic.jpg', quality=90, optimize=True)
    if args.preview:
        full_img.save(args.preview)


if __name__ == '__main__':
    main()
