from setuptools import setup, find_packages

setup(
    name             = 'mind-sentinel',
    version          = '2.0.0',
    description      = 'mINd-SENTinel — Offline SMS & Call Log Intent Analyzer · Nous Loop Solutions',
    author           = 'Nous Loop Solutions',
    packages         = find_packages(exclude=['tests*']),
    install_requires = open('requirements.txt').read().splitlines(),
    entry_points     = {
        'console_scripts': [
            'sentinel         = sentinel.cli:main',
            'sentinel-uplifts = sentinel.uplifts.extractor:main',
        ],
    },
    python_requires  = '>=3.10',
    classifiers      = [
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
