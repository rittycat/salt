from setuptools import setup

setup(
    name='docker-firewall-manager',
    version='1.0',
    packages=['dfm'],
    install_requires=[
        'docker',
        'typer',
        'shellingham'
    ],
    entry_points={
      'console_scripts': ['dfmd=dfm.dfmd:app']
    },
    author='Rittycat',
    author_email='ritty.blackmore@nitrado.net',
    description='Manages firewall rules for a docker bridge network'
)
