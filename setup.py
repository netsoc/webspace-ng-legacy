import setuptools

with open('requirements.txt') as req_file:
    requirements = req_file.read()

setuptools.setup(
    name='webspace-ng',
    version='0.0.1',
    author="Jack O'Sullivan",
    author_email='jackos1998@gmail.com',
    description='Next generation webspace management',
    packages=setuptools.find_packages(),
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'webspaced=webspace_ng.daemon:main',
            'webspace-cli=webspace_ng.cli:main',
        ]
    }
)
