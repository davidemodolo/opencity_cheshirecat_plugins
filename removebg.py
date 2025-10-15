#!/usr/bin/env python3
"""resize/crop PNGs to square and make white pixels transparent

Usage:
  python removebg.py --input ./input --output ./output --size 340 --tolerance 0

This script finds all PNG files in the input directory (non-recursive),
resizes them so their smallest side equals `size`, center-crops to `size x size`,
and converts pure-white (or near-white, depending on `--tolerance`) pixels to transparent.
"""

from PIL import Image
from PIL import ImageFilter
import argparse
import os
import sys


def process_image(in_path, out_path, size=340, tolerance=0.0, smoothing=0.0):
	img = Image.open(in_path).convert('RGBA')
	w, h = img.size

	# scale so the smallest dimension == size
	scale = size / float(min(w, h))
	new_w = max(1, int(round(w * scale)))
	new_h = max(1, int(round(h * scale)))
	if (new_w, new_h) != (w, h):
		img = img.resize((new_w, new_h), Image.LANCZOS)

	# center crop to size x size
	left = max(0, (img.width - size) // 2)
	top = max(0, (img.height - size) // 2)
	right = left + size
	bottom = top + size
	img = img.crop((left, top, right, bottom))

	# Replace white pixels with transparent. Use tolerance to allow near-white.
	# New semantics: `tolerance` is a float in 0.0..1.0 where 1.0 means only pure white
	# is removed (i.e. 255 threshold), and 0.0 means all pixels become transparent.
	# For backward compatibility, if an integer > 1 is passed (0..255 style),
	# we convert it to the 0..1 range by dividing by 255.
	datas = list(img.getdata())
	# We'll build an alpha mask (0..255) based on whiteness threshold, then
	# optionally smooth it and apply back to the image.
	alpha_mask = Image.new('L', img.size)
	mask_data = []
	new_data = []
	# Normalize tolerance to 0.0..1.0
	try:
		_tol = float(tolerance)
	except Exception:
		_tol = 0.0
	# If user passed legacy 0..255 integer (common), convert to 0..1
	if _tol > 1.0:
		_tol = max(0.0, min(1.0, _tol / 255.0))
	# Compute threshold: when _tol == 1.0 -> threshold = 255 (only pure white removed)
	# when _tol == 0.0 -> threshold = 0 (all pixels removed)
	threshold = int(round(255 * _tol))
	for item in datas:
		r, g, b, a = item
		# If pixel is sufficiently white, set mask to 0 (transparent), else 255
		if r >= threshold and g >= threshold and b >= threshold:
			mask_data.append(0)
		else:
			mask_data.append(255)

	alpha_mask.putdata(mask_data)

	# Apply smoothing by blurring the mask. smoothing is 0.0..1.0 -> radius 0..5
	try:
		s = float(smoothing)
	except Exception:
		s = 0.0
	s = max(0.0, min(1.0, s))
	if s > 0.0:
		max_radius = 5.0
		radius = s * max_radius
		alpha_mask = alpha_mask.filter(ImageFilter.GaussianBlur(radius))

	# Recombine RGB with new alpha mask
	rgb = img.convert('RGB')
	r_final = []
	mask_pixels = list(alpha_mask.getdata())
	for (r, g, b, a), m in zip(datas, mask_pixels):
		# use mask value as alpha
		r_final.append((r, g, b, m))
	img.putdata(r_final)

	img.putdata(new_data)
	img.save(out_path, 'PNG')


def main():
	parser = argparse.ArgumentParser(description='Resize/crop PNGs and make white transparent')
	parser.add_argument('--input', '-i', default='.', help='Input directory containing PNGs')
	parser.add_argument('--output', '-o', default='./out', help='Output directory to save processed PNGs')
	parser.add_argument('--size', '-s', type=int, default=340, help='Output square size (default 340)')
	parser.add_argument('--tolerance', '-t', type=float, default=1.0, help='Tolerance for whiteness as a percentage (0.0..1.0). 1.0 means only pure white; 0.0 means all pixels become transparent. Legacy 0..255 integers are supported.')
	parser.add_argument('--recursive', '-r', action='store_true', help='Search input directory recursively')
	parser.add_argument('--smoothing', '-m', type=float, default=0.0, help='Edge smoothing (0.0..1.0). Applies Gaussian blur to alpha mask to smooth edges.')

	args = parser.parse_args()

	in_dir = os.path.abspath(args.input)
	out_dir = os.path.abspath(args.output)
	size = int(args.size)
	# tolerance is accepted as float 0.0..1.0 (percentage of whiteness to keep)
	tol = args.tolerance

	if not os.path.isdir(in_dir):
		print(f"Input directory does not exist: {in_dir}")
		sys.exit(1)

	os.makedirs(out_dir, exist_ok=True)

	# Gather PNG files
	pngs = []
	if args.recursive:
		for root, _, files in os.walk(in_dir):
			for f in files:
				if f.lower().endswith('.png'):
					pngs.append(os.path.join(root, f))
	else:
		for f in os.listdir(in_dir):
			if f.lower().endswith('.png'):
				pngs.append(os.path.join(in_dir, f))

	if not pngs:
		print('No PNG files found in', in_dir)
		return

	for src in pngs:
		rel_name = os.path.relpath(src, in_dir)
		# flatten nested paths for non-recursive mode; for recursive keep the directory structure
		if args.recursive:
			dest_rel = rel_name
		else:
			dest_rel = os.path.basename(rel_name)

		dest_path = os.path.join(out_dir, dest_rel)
		dest_dir = os.path.dirname(dest_path)
		if dest_dir and not os.path.isdir(dest_dir):
			os.makedirs(dest_dir, exist_ok=True)

		try:
			process_image(src, dest_path, size=size, tolerance=tol, smoothing=args.smoothing)
			print(f'Processed: {src} -> {dest_path}')
		except Exception as e:
			print(f'Failed to process {src}: {e}')


if __name__ == '__main__':
	main()

