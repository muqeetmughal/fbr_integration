# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in fbr_integration/__init__.py
from fbr_integration import __version__ as version

setup(
	name="fbr_integration",
	version=version,
	description="FBR integration is the process of connecting a business\'s transactional systems, such as Point of Sale (POS) or accounting software, directly to the Federal Board of Revenue (FBR) of Pakistan\'s central database.",
	author="infintrixtech.com",
	author_email="muqeetmughal786@gmail.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
