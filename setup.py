from setuptools import setup, find_packages

setup(
    name="pkgeditor",
    version="1.0.0",
    description="Cross-platform PlayStation Package (.pkg), SFO, and GP4 Editor",
    author="PkgEditor Contributors",
    packages=find_packages(),
    install_requires=[
        "PyQt5>=5.15.0",
        "cryptography>=3.4.0",
    ],
    extras_require={
        "pyqt6": ["PyQt6>=6.0.0"],
        "pyside6": ["PySide6>=6.0.0"],
    },
    entry_points={
        "console_scripts": [
            "pkgeditor=pkgeditor.__main__:main",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Utilities",
    ],
)
