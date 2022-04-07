import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

install_requires = [
    'caproto>=0.8.1',
    'numpy>=1.21.0',
]

setuptools.setup(
    name="speca",
    version="0.0.1",
    author="SangWoo Kim",
    author_email="sngwkim915@gmail.com",
    description = "Converts motors and counters provided in SPEC Server to EPICS PV",
    long_description = long_description,
    long_description_content_type = "text/markdown",
    url = "https://github.com/physwkim/speca",
    project_urls = {
        "Bug Tracker" : "https://github.com/physwkim/speca/issues",
    },
    classifiers = [
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=setuptools.find_packages(where="."),
    python_requires=">=3.7",
    install_requires=install_requires,
)

