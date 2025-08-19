#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name="ali_lcd_device",
    version="0.1.0",
    description="ALi Corp 0402:3922 LCD device communication library",
    author="Linux Control Team",
    author_email="info@example.com",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "pyusb>=1.2.0",
        "numpy>=1.19.0",
        "pillow>=8.0.0",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.6",
)
