from setuptools import setup

setup(
    name='kanimaji',
    version='0.1',
    description=(
        "A small utility for transforming KanjiVG images into animated SVG "
        "or GIF files, or SVGs that can easily animated via Javascript "
        "(with no library dependency!)."
    ),
    license='MIT',
    scripts=[
        'kanimaji.py',
        'bezier_cubic.py',
        'settings.py',
    ],
    install_requires=[
        'svg.path',
        'tqdm',
    ],
    zip_safe=False,
)
