# Kanimaji

## Generation of animations

This is a small utility for transforming KanjiVG images into animated SVG or GIF files, or SVGs that can easily animated via Javascript (with no library dependency!).

 * SVG samples (animated via CSS, no SMIL/<animate> element):

![084b8 SVG](http://maurimo.github.io/kanimaji/samples/084b8_anim.svg)
![08972 SVG](http://maurimo.github.io/kanimaji/samples/08972_anim.svg)

 * GIF samples:

![084b8 GIF](http://maurimo.github.io/kanimaji/samples/084b8_anim.gif)
![08972 GIF](http://maurimo.github.io/kanimaji/samples/08972_anim.gif)

(these GIFs are 150x150 and have size 24k and 30k. With transparent background the generated image are quite bigger ~220k unluckily).

 * Javascript controlled SVG:

See the [Demo on the Project Page](http://maurimo.github.io/kanimaji/index.html).


## Usage

First install by running `python setup.py install`

To download the KanjiVG SVGs to be animated, run `git submodule update --init --recursive`.

If you want to generate animated GIFs, you will need to separately install these packages:
 * [svgexport](https://github.com/shakiba/svgexport) Node.js library for exporting SVG to PNG.
 * [ImageMagick](https://www.imagemagick.org) to merge PNGs into a GIF.
 * [Gifsicle](https://www.lcdf.org/gifsicle/) to optimize GIF size.

Then just run
```
./kanimaji.py --svg --js-svg --gif
```
with whichever types of animations you want to generate as parameters, and the files will appear in `./converted/`.

## Settings

Just edit the settings.py file, all settings are explained there.

## License

This software is formally released under MIT/BSD (at your option).
You are free to do what you want with this program, please credit my work if you use it.
If you find it useful and feel like, you may give a donation on my github page!
