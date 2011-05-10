#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name = "libinst.repo.deb",
    version = "1.0",
    author = "Jan Wenzel",
    author_email = "wenzel@gonicus.de",
    description = "Repository and installation abstraction library",
    long_description = """
This library handles the installation, configuration and repositories
for various systems in your setup.
""",
    license = "LGPL",
    url = "http://www.gosa-project.org",
    classifiers = [
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: System :: Systems Administration',
        'Topic :: System :: Software Distribution',
        'Topic :: System :: Monitoring',
    ],

    download_url = "http://oss.gonicus.de/pub/gosa",
    packages = find_packages('src', exclude=['examples', 'tests']),
    namespace_package = 'libinst',
    package_dir={'': 'src'},

    include_package_data = True,
    package_data = {
    },

    test_suite = "nose.collector",
    zip_safe = False,

    setup_requires = ['nose', 'NoseXUnit', 'pylint'],
    install_requires = [
        'zope.interface>=3.5',
        'sqlalchemy',
        'gosa.agent',
        'python-gnupg',
        'python-debian',
        'pytz',
    ],


    entry_points = """
        [libinst.repository]
        libinst.debian_handler = libinst.repo.deb.main:DebianHandler
    """
)
